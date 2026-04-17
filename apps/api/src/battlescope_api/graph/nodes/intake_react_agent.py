from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI
from langgraph.graph.state import CompiledStateGraph
from langgraph.prebuilt import create_react_agent

from battlescope_api.models.company_profile import CompanyProfileLlm
from battlescope_api.settings import Settings
from battlescope_api.tools.alphavantage_client import (
    AlphaVantageClient,
    format_earnings_transcript_for_llm,
)
from battlescope_api.tools.firecrawl_client import FirecrawlClient
from battlescope_api.tools.tavily_client import TavilyClient

logger = logging.getLogger(__name__)

_PROMPTS_DIR = Path(__file__).resolve().parents[2] / "prompts"
INTAKE_REACT_RECURSION_LIMIT = 18


def load_intake_react_system_prompt() -> str:
    return (_PROMPTS_DIR / "intake_react_system.md").read_text(encoding="utf-8")


def _format_tavily_block(payload: dict) -> str:
    lines: list[str] = []
    for idx, item in enumerate(payload.get("results") or [], start=1):
        title = item.get("title") or ""
        url = item.get("url") or ""
        content = (item.get("content") or "").strip()
        lines.append(f"{idx}. {title}\n   URL: {url}\n   Snippet: {content[:800]}")
    return "\n\n".join(lines) if lines else "(no Tavily results)"


def _firecrawl_markdown(payload: dict) -> str:
    if payload.get("success") is False:
        err = payload.get("error") or "unknown_error"
        return f"(scrape failed: {err})"
    data = payload.get("data") or {}
    md = data.get("markdown") or payload.get("markdown") or ""
    return str(md)


def _clip(text: str, max_chars: int) -> str:
    if len(text) <= max_chars:
        return text
    return text[: max_chars - 20] + "\n...[truncated]..."


def build_intake_user_brief(
    *,
    company_name: str,
    company_url: str | None,
    url_normalized: str | None,
    domain: str | None,
    display_name: str,
    tavily_enabled: bool = False,
    firecrawl_enabled: bool = False,
    alphavantage_enabled: bool = False,
) -> str:
    def _on(off: bool) -> str:
        return "yes — tool is available this run" if off else "no — not configured"

    av_line = _on(alphavantage_enabled)
    if alphavantage_enabled:
        av_line += (
            ". **When the target is a US-listed public company and Tavily/snippets give a "
            "high-confidence equity ticker, call `earnings_call_transcript` once** with that ticker "
            "and a recent **completed** fiscal quarter before you stop research (unless clearly private "
            "or ticker is ambiguous—then note in uncertainties)."
        )

    lines = [
        "## Target",
        "Human input (verbatim): **company_name**, **company_url**. "
        "Server-normalized from URL: **normalized_url**, **inferred_domain**. "
        "**display_name** = name if provided, else a short label from domain, else unknown.",
        "",
        f"- company_name (human): {company_name or '(none)'}",
        f"- company_url (human, raw): {company_url or '(none)'}",
        f"- normalized_url (server): {url_normalized or '(none)'}",
        f"- inferred_domain (server): {domain or '(none)'}",
        f"- display_name (convenience): {display_name}",
        "",
        "## Enabled backends (this run)",
        f"- Tavily web search: {_on(tavily_enabled)}",
        f"- Firecrawl `scrape_url`: {_on(firecrawl_enabled)}",
        f"- Alpha Vantage `earnings_call_transcript`: {av_line}",
        "",
        "Use tools to research, then let the structured output step record the profile.",
    ]
    return "\n".join(lines)


def build_intake_react_graph(
    settings: Settings,
    tavily: TavilyClient,
    firecrawl: FirecrawlClient,
    alphavantage: AlphaVantageClient,
) -> CompiledStateGraph:
    max_ctx = settings.intake_context_max_chars

    @tool
    async def tavily_search(query: str, max_results: int = 6) -> str:
        """Search the public web. Pass a focused natural-language query (company, product, pricing, news)."""
        bounded = max(1, min(int(max_results), 10))
        try:
            payload = await tavily.search(query, max_results=bounded)
        except Exception as exc:
            logger.warning("intake_react_tavily_tool_error", extra={"error": str(exc)})
            return f"Tavily error ({type(exc).__name__}): {exc}"
        return _format_tavily_block(payload)

    @tool
    async def scrape_url(url: str) -> str:
        """Fetch markdown for one page. Use the company homepage, /pricing, /product, or docs URL."""
        u = (url or "").strip()
        if not u.startswith(("http://", "https://")):
            return "(scrape_url requires an absolute http(s) URL.)"
        try:
            payload = await firecrawl.scrape_url(u)
        except Exception as exc:
            logger.warning("intake_react_firecrawl_tool_error", extra={"error": str(exc)})
            return f"Scrape error ({type(exc).__name__}): {exc}"
        md = _firecrawl_markdown(payload)
        return _clip(md, max_ctx) if md.strip() else "(empty markdown)"

    @tool
    async def earnings_call_transcript(symbol: str, quarter: str) -> str:
        """
        **Primary source:** earnings call transcript for a US-listed equity (Alpha Vantage).

        Call this **once per run** when the user message says Alpha Vantage is enabled and you have a
        **credible ticker** (from Tavily/snippets). Requires `symbol` (e.g. IBM) and fiscal `quarter`
        as YYYYQ1..YYYYQ4 (e.g. 2025Q4). Use tavily_search first if you need the ticker.

        Calendar context: runs may occur in April 2026—prefer the latest **completed** fiscal quarter
        that is likely to have a full transcript in the API (e.g. **2025Q4** or **2025Q3**), not the
        current in-progress quarter, which is often missing or unreliable.
        """
        try:
            payload = await alphavantage.earnings_call_transcript(symbol, quarter)
        except Exception as exc:
            logger.warning("intake_react_alphavantage_tool_error", extra={"error": str(exc)})
            return f"Alpha Vantage error ({type(exc).__name__}): {exc}"
        return format_earnings_transcript_for_llm(payload, max_chars=max_ctx)

    if not settings.openai_api_key:
        raise RuntimeError("OPENAI_API_KEY is required for Intake ReAct")

    model = ChatOpenAI(
        api_key=settings.openai_api_key,
        base_url=settings.openai_sdk_base_url,
        model=settings.openai_model,
        temperature=0.2,
    )

    tools: list = [tavily_search, scrape_url]
    if settings.alphavantage_api_key:
        tools.append(earnings_call_transcript)
    else:
        logger.info("intake_react_alphavantage_tool_omitted", extra={"reason": "missing_api_key"})

    return create_react_agent(
        model,
        tools,
        prompt=load_intake_react_system_prompt(),
        response_format=CompanyProfileLlm,
        name="intake_research",
    )


def _last_ai_text(messages: list[Any]) -> str:
    for m in reversed(messages):
        if isinstance(m, AIMessage) and m.content:
            if isinstance(m.content, str):
                return m.content
            if isinstance(m.content, list):
                parts: list[str] = []
                for block in m.content:
                    if isinstance(block, dict) and block.get("type") == "text":
                        parts.append(str(block.get("text", "")))
                return "\n".join(parts)
    return ""


async def run_intake_react_research(
    *,
    settings: Settings,
    tavily: TavilyClient,
    firecrawl: FirecrawlClient,
    alphavantage: AlphaVantageClient,
    human_brief: str,
    recursion_limit: int = INTAKE_REACT_RECURSION_LIMIT,
) -> tuple[CompanyProfileLlm | None, list[str]]:
    """
    Run the ReAct subgraph and return a validated profile if structured output succeeded.

    Returns ``(None, notes)`` on failure or missing structured response.
    """
    notes: list[str] = []
    graph = build_intake_react_graph(settings, tavily, firecrawl, alphavantage)
    try:
        out: dict[str, Any] = await graph.ainvoke(
            {"messages": [HumanMessage(content=human_brief)]},
            config={"recursion_limit": recursion_limit},
        )
    except Exception as exc:
        logger.warning("intake_react_graph_invoke_failed", extra={"error": str(exc)})
        notes.append(f"Intake ReAct failed ({type(exc).__name__}): {exc}")
        return None, notes

    sr = out.get("structured_response")
    if sr is None:
        tail = _last_ai_text(list(out.get("messages") or []))
        if "need more steps" in tail.lower():
            notes.append(
                "Intake ReAct hit the step/recursion ceiling before finishing; try a narrower request or raise limits."
            )
        else:
            notes.append("Intake ReAct finished without structured_response; falling back to heuristics.")
        return None, notes

    if isinstance(sr, CompanyProfileLlm):
        return sr, notes
    if isinstance(sr, dict):
        try:
            return CompanyProfileLlm.model_validate(sr), notes
        except Exception as exc:
            notes.append(f"Structured response could not be validated ({type(exc).__name__}): {exc}")
            return None, notes

    notes.append(f"Unexpected structured_response type: {type(sr).__name__}")
    return None, notes
