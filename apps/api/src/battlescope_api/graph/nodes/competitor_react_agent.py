from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI
from langgraph.graph.state import CompiledStateGraph
from langgraph.prebuilt import create_react_agent

from battlescope_api.models.competitor_landscape import CompetitorLandscapeLlm
from battlescope_api.settings import Settings
from battlescope_api.tools.firecrawl_client import FirecrawlClient
from battlescope_api.tools.newsapi_client import NewsApiClient, format_newsapi_block
from battlescope_api.tools.tavily_client import TavilyClient

logger = logging.getLogger(__name__)

_PROMPTS_DIR = Path(__file__).resolve().parents[2] / "prompts"


def load_competitor_react_system_prompt() -> str:
    return (_PROMPTS_DIR / "competitor_react_system.md").read_text(encoding="utf-8")


def format_tavily_block_for_prompt(payload: dict) -> str:
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


async def fetch_tavily_top10_seed_block(
    *,
    tavily: TavilyClient,
    company_name: str,
    max_chars: int,
) -> str:
    """
    Mandatory first research step: one Tavily query aimed at a broad ~6 competitor list.
    Injected above the ReAct brief so the model always starts from a wide candidate pool.
    """
    name = (company_name or "").strip()
    if not name:
        return ""
    primary = f"top 10 competitors of {name}"
    fallback = f"{name} main competitors compared list"
    try:
        payload = await tavily.search(primary, max_results=10)
        results = payload.get("results") or []
        if len(results) < 3:
            payload = await tavily.search(fallback, max_results=10)
    except Exception as exc:
        logger.warning("tavily_top10_seed_failed", extra={"error": str(exc)})
        return (
            f"### Tavily seed (top ~10) — **failed**\n"
            f"`{primary}` → {type(exc).__name__}: {exc}\n"
            "Continue with `tavily_search` / `news_search` in the ladder."
        )
    block = format_tavily_block_for_prompt(payload)
    header = (
        "### Tavily seed (step 0 — **top ~10 candidates**)\n"
        f"**Query used:** `{primary}` (max_results=10). "
        "From this pool + follow-up tools, **narrow to 5–6** best grounded peers (minimum 3).\n\n"
    )
    return _clip(header + block, max_chars)


def build_competitor_react_user_brief(
    *,
    company_name: str,
    company_url: str,
    tavily_enabled: bool,
    newsapi_enabled: bool,
    firecrawl_enabled: bool,
    packed_context: str,
) -> str:
    def _on(ok: bool) -> str:
        return "yes — tool is available this run" if ok else "no — not configured"

    return "\n".join(
        [
            "## Research task",
            "Discover **5–6 competitors** of the **target** (minimum **3** when evidence is thin). "
            "A **Tavily top-10 seed** block may appear above — treat it as the **wide candidate pool**, then "
            "**verify and filter** with tools. Map each final peer to **home SEC Item 1A risk themes** "
            "from the packed context (see system prompt for mapping rules).",
            "",
            "## Funnel (summary — full ladder in system prompt)",
            "- **Step 0:** Tavily seed above (when present) lists ~10 candidates — **do not skip** using it as the starting set.",
            "- **Steps 1+:** Corroborate with `tavily_search`, `news_search` (when enabled), `scrape_url` on strong URLs; "
            "go **broad → narrow** until you have **5–6** best grounded names (or ≥3 if evidence caps out).",
            "- Use **Firecrawl** on comparison / analyst pages when enabled to pull **names** from page body, not only snippets.",
            "- **If you cannot find three** after that ladder: return **only** grounded names (never pad with unrelated "
            "megacaps). Explain briefly in **`target_company_context_note`**; use weak/speculative grades and lower "
            "confidence. The product will show **degraded** until there are at least three distinct peers.",
            "",
            "## Enabled backends (this run)",
            f"- Tavily `tavily_search`: {_on(tavily_enabled)}",
            f"- NewsAPI `news_search`: {_on(newsapi_enabled)}",
            f"- Firecrawl `scrape_url`: {_on(firecrawl_enabled)}",
            "",
            "## Target identifiers (verbatim / server)",
            f"- company_name: {company_name or '(none)'}",
            f"- company_url (raw): {company_url or '(none)'}",
            "",
            "## Packed context (from prior pipeline)",
            packed_context.strip(),
        ]
    )


def build_competitor_react_graph(
    settings: Settings,
    tavily: TavilyClient,
    newsapi: NewsApiClient,
    firecrawl: FirecrawlClient,
) -> CompiledStateGraph:
    max_ctx = settings.competitor_context_max_chars

    @tool
    async def tavily_search(query: str, max_results: int = 10) -> str:
        """Search the public web for competitors, market maps, analyst comparisons, or company facts. Use up to 10 results for broad peer lists."""
        bounded = max(1, min(int(max_results), 10))
        try:
            payload = await tavily.search(query, max_results=bounded)
        except Exception as exc:
            logger.warning("competitor_react_tavily_tool_error", extra={"error": str(exc)})
            return f"Tavily error ({type(exc).__name__}): {exc}"
        return _clip(format_tavily_block_for_prompt(payload), max_ctx)

    @tool
    async def news_search(query: str, page_size: int = 15) -> str:
        """Search recent English news articles (NewsAPI). Use focused queries: company + competitor/industry terms."""
        bounded = max(1, min(int(page_size), 30))
        try:
            payload = await newsapi.everything(query, page_size=bounded)
        except Exception as exc:
            logger.warning("competitor_react_newsapi_tool_error", extra={"error": str(exc)})
            return f"NewsAPI error ({type(exc).__name__}): {exc}"
        return _clip(format_newsapi_block(payload, max_chars=max_ctx), max_ctx)

    @tool
    async def scrape_url(url: str) -> str:
        """Fetch markdown for one page (press release, competitor about page, investor site)."""
        u = (url or "").strip()
        if not u.startswith(("http://", "https://")):
            return "(scrape_url requires an absolute http(s) URL.)"
        try:
            payload = await firecrawl.scrape_url(u)
        except Exception as exc:
            logger.warning("competitor_react_firecrawl_tool_error", extra={"error": str(exc)})
            return f"Scrape error ({type(exc).__name__}): {exc}"
        md = _firecrawl_markdown(payload)
        return _clip(md, max_ctx) if md.strip() else "(empty markdown)"

    if not settings.openai_api_key:
        raise RuntimeError("OPENAI_API_KEY is required for competitor ReAct")

    model = ChatOpenAI(
        api_key=settings.openai_api_key,
        base_url=settings.openai_sdk_base_url,
        model=settings.openai_model,
        temperature=0.15,
    )

    tools: list = [tavily_search]
    if settings.newsapi_api_key:
        tools.append(news_search)
        logger.info("competitor_react_newsapi_tool_registered")
    else:
        logger.info("competitor_react_newsapi_tool_omitted", extra={"reason": "missing_api_key"})
    if settings.firecrawl_api_key:
        tools.append(scrape_url)
    else:
        logger.info("competitor_react_firecrawl_tool_omitted", extra={"reason": "missing_api_key"})

    return create_react_agent(
        model,
        tools,
        prompt=load_competitor_react_system_prompt(),
        response_format=CompetitorLandscapeLlm,
        name="competitor_research",
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


async def run_competitor_react_research(
    *,
    settings: Settings,
    tavily: TavilyClient,
    newsapi: NewsApiClient,
    firecrawl: FirecrawlClient,
    human_brief: str,
    recursion_limit: int | None = None,
) -> tuple[CompetitorLandscapeLlm | None, list[str]]:
    """
    Run the competitor ReAct subgraph; return validated ``CompetitorLandscapeLlm`` or None.
    """
    notes: list[str] = []
    limit = recursion_limit if recursion_limit is not None else settings.competitor_react_recursion_limit
    graph = build_competitor_react_graph(settings, tavily, newsapi, firecrawl)
    try:
        out: dict[str, Any] = await graph.ainvoke(
            {"messages": [HumanMessage(content=human_brief)]},
            config={"recursion_limit": limit},
        )
    except Exception as exc:
        logger.warning("competitor_react_graph_invoke_failed", extra={"error": str(exc)})
        notes.append(f"Competitor ReAct failed ({type(exc).__name__}): {exc}")
        return None, notes

    sr = out.get("structured_response")
    if sr is None:
        tail = _last_ai_text(list(out.get("messages") or []))
        if "need more steps" in tail.lower():
            notes.append(
                "Competitor ReAct hit the step/recursion ceiling before finishing; raise limits or narrow case."
            )
        else:
            notes.append("Competitor ReAct finished without structured_response.")
        return None, notes

    if isinstance(sr, CompetitorLandscapeLlm):
        return sr, notes
    if isinstance(sr, dict):
        try:
            return CompetitorLandscapeLlm.model_validate(sr), notes
        except Exception as exc:
            notes.append(f"Structured response could not be validated ({type(exc).__name__}): {exc}")
            return None, notes

    notes.append(f"Unexpected structured_response type: {type(sr).__name__}")
    return None, notes
