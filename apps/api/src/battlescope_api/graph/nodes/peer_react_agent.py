from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI
from langgraph.graph.state import CompiledStateGraph
from langgraph.prebuilt import create_react_agent

from battlescope_api.graph.nodes.competitor_react_agent import (
    _clip,
    _firecrawl_markdown,
    format_tavily_block_for_prompt,
)
from battlescope_api.models.peer_research_digest import PeerResearchDigestLlm
from battlescope_api.settings import Settings
from battlescope_api.tools.alphavantage_client import AlphaVantageClient, format_earnings_transcript_for_llm
from battlescope_api.tools.firecrawl_client import FirecrawlClient
from battlescope_api.tools.newsapi_client import NewsApiClient, format_newsapi_block
from battlescope_api.tools.tavily_client import TavilyClient

logger = logging.getLogger(__name__)

_PROMPTS_DIR = Path(__file__).resolve().parents[2] / "prompts"


def load_peer_react_system_prompt() -> str:
    return (_PROMPTS_DIR / "peer_react_system.md").read_text(encoding="utf-8")


def build_peer_react_user_brief(
    *,
    peer_display_name: str,
    peer_ticker: str | None,
    peer_landscape_json: str,
    home_company_name: str,
    home_summary_clip: str,
    home_sec_bullets_clip: str,
    tavily_enabled: bool,
    newsapi_enabled: bool,
    firecrawl_enabled: bool,
    alphavantage_enabled: bool,
) -> str:
    def _on(ok: bool) -> str:
        return "yes — tool is available this run" if ok else "no — not configured"

    av_line = _on(alphavantage_enabled)
    if alphavantage_enabled:
        av_line += (
            ". **When the peer is a plausible US-listed equity**, call `earnings_call_transcript` **at most once** "
            "with that peer’s **symbol** (from the brief’s ticker if credible, else confirm via Tavily) and a recent "
            "**completed** fiscal `quarter` as YYYYQ1..YYYYQ4 (e.g. 2025Q4). Skip if private, ADR ambiguity, or "
            "symbol unclear—note in `evidence_notes`."
        )

    return "\n".join(
        [
            "## Research task (one peer only)",
            f"Produce a **PeerResearchDigest** for this **single** peer: **{peer_display_name}**.",
            f"- Peer ticker (if known): {peer_ticker or '(unknown)'}",
            "",
            "## Peer context from prior competitor-discovery output (JSON)",
            peer_landscape_json.strip(),
            "",
            "## Home / target company (for comparison only — not primary research subject)",
            f"- name: {home_company_name or '(none)'}",
            f"- summary (clip):\n{home_summary_clip.strip()}",
            "",
            "## Home 10-K Item 1A theme bullets (clip — context only)",
            home_sec_bullets_clip.strip() or "(none)",
            "",
            "## Enabled backends (this run)",
            f"- Tavily `tavily_search`: {_on(tavily_enabled)}",
            f"- NewsAPI `news_search`: {_on(newsapi_enabled)}",
            f"- Firecrawl `scrape_url`: {_on(firecrawl_enabled)}",
            f"- Alpha Vantage `earnings_call_transcript`: {av_line}",
        ]
    )


def build_peer_react_graph(
    settings: Settings,
    tavily: TavilyClient,
    newsapi: NewsApiClient,
    firecrawl: FirecrawlClient,
    alphavantage: AlphaVantageClient,
    *,
    agent_graph_name: str = "peer_deep_research",
) -> CompiledStateGraph:
    max_ctx = settings.peer_research_context_max_chars

    @tool
    async def tavily_search(query: str, max_results: int = 6) -> str:
        """Search the web for the peer: product, pricing, positioning, news, comparisons."""
        bounded = max(1, min(int(max_results), 10))
        try:
            payload = await tavily.search(query, max_results=bounded)
        except Exception as exc:
            logger.warning("peer_react_tavily_tool_error", extra={"error": str(exc)})
            return f"Tavily error ({type(exc).__name__}): {exc}"
        return _clip(format_tavily_block_for_prompt(payload), max_ctx)

    @tool
    async def news_search(query: str, page_size: int = 15) -> str:
        """News articles about the peer (launches, partnerships, category positioning)."""
        bounded = max(1, min(int(page_size), 30))
        try:
            payload = await newsapi.everything(query, page_size=bounded)
        except Exception as exc:
            logger.warning("peer_react_newsapi_tool_error", extra={"error": str(exc)})
            return f"NewsAPI error ({type(exc).__name__}): {exc}"
        return _clip(format_newsapi_block(payload, max_chars=max_ctx), max_ctx)

    @tool
    async def scrape_url(url: str) -> str:
        """Fetch markdown for one high-value URL (about, pricing, docs, investor)."""
        u = (url or "").strip()
        if not u.startswith(("http://", "https://")):
            return "(scrape_url requires an absolute http(s) URL.)"
        try:
            payload = await firecrawl.scrape_url(u)
        except Exception as exc:
            logger.warning("peer_react_firecrawl_tool_error", extra={"error": str(exc)})
            return f"Scrape error ({type(exc).__name__}): {exc}"
        md = _firecrawl_markdown(payload)
        return _clip(md, max_ctx) if md.strip() else "(empty markdown)"

    @tool
    async def earnings_call_transcript(symbol: str, quarter: str) -> str:
        """
        **Primary source:** earnings call transcript for a US-listed equity (Alpha Vantage).

        Call **at most once** for **this peer** when the Human brief says Alpha Vantage is enabled and you have a
        **credible symbol** for the peer (brief ticker or Tavily-confirmed). Use fiscal `quarter` as YYYYQ1..YYYYQ4
        for a recent **completed** quarter likely to have a full transcript (not the current in-progress quarter if
        the API often returns empty).
        """
        try:
            payload = await alphavantage.earnings_call_transcript(symbol, quarter)
        except Exception as exc:
            logger.warning("peer_react_alphavantage_tool_error", extra={"error": str(exc)})
            return f"Alpha Vantage error ({type(exc).__name__}): {exc}"
        return format_earnings_transcript_for_llm(payload, max_chars=max_ctx)

    if not settings.openai_api_key:
        raise RuntimeError("OPENAI_API_KEY is required for peer ReAct")

    model = ChatOpenAI(
        api_key=settings.openai_api_key,
        base_url=settings.openai_sdk_base_url,
        model=settings.openai_model,
        temperature=0.12,
    )

    tools: list = [tavily_search]
    if settings.newsapi_api_key:
        tools.append(news_search)
    else:
        logger.debug(
            "peer_react_newsapi_tool_omitted",
            extra={"reason": "missing_api_key", "graph": agent_graph_name},
        )
    if settings.firecrawl_api_key:
        tools.append(scrape_url)
    else:
        logger.debug(
            "peer_react_firecrawl_tool_omitted",
            extra={"reason": "missing_api_key", "graph": agent_graph_name},
        )
    if settings.alphavantage_api_key:
        tools.append(earnings_call_transcript)
    else:
        logger.debug(
            "peer_react_alphavantage_tool_omitted",
            extra={"reason": "missing_api_key", "graph": agent_graph_name},
        )

    return create_react_agent(
        model,
        tools,
        prompt=load_peer_react_system_prompt(),
        response_format=PeerResearchDigestLlm,
        name=agent_graph_name,
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


async def run_peer_react_research(
    *,
    settings: Settings,
    tavily: TavilyClient,
    newsapi: NewsApiClient,
    firecrawl: FirecrawlClient,
    alphavantage: AlphaVantageClient,
    human_brief: str,
    recursion_limit: int | None = None,
    peer_key: str | None = None,
    peer_display_name: str | None = None,
) -> tuple[PeerResearchDigestLlm | None, list[str]]:
    notes: list[str] = []
    pk = peer_key or "unknown_peer"
    pname = (peer_display_name or "").strip() or pk
    log_extra = {"peer_key": pk, "peer_display_name": pname}
    logger.info("peer_react_session_start", extra=log_extra)

    limit = recursion_limit if recursion_limit is not None else settings.peer_react_recursion_limit
    # Unique graph name per peer so LangSmith / traces show three distinct subgraphs, not one repeated.
    safe_name = "".join(c if c.isalnum() or c in ("-", "_") else "_" for c in pk)[:60]
    graph = build_peer_react_graph(
        settings,
        tavily,
        newsapi,
        firecrawl,
        alphavantage,
        agent_graph_name=f"peer_deep_{safe_name}",
    )
    try:
        out: dict[str, Any] = await graph.ainvoke(
            {"messages": [HumanMessage(content=human_brief)]},
            config={"recursion_limit": limit},
        )
    except Exception as exc:
        logger.warning("peer_react_graph_invoke_failed", extra={**log_extra, "error": str(exc)})
        notes.append(f"Peer ReAct failed ({type(exc).__name__}): {exc}")
        logger.info("peer_react_session_end", extra={**log_extra, "outcome": "invoke_error"})
        return None, notes

    sr = out.get("structured_response")
    if sr is None:
        tail = _last_ai_text(list(out.get("messages") or []))
        if "need more steps" in tail.lower():
            notes.append("Peer ReAct hit recursion ceiling before structured output.")
        else:
            notes.append("Peer ReAct finished without structured_response.")
        logger.info("peer_react_session_end", extra={**log_extra, "outcome": "no_structured_response"})
        return None, notes

    if isinstance(sr, PeerResearchDigestLlm):
        logger.info(
            "peer_react_session_end",
            extra={**log_extra, "outcome": "ok", "ahead_axes": len(sr.ahead_axes or [])},
        )
        return sr, notes
    if isinstance(sr, dict):
        try:
            validated = PeerResearchDigestLlm.model_validate(sr)
            logger.info(
                "peer_react_session_end",
                extra={**log_extra, "outcome": "ok", "ahead_axes": len(validated.ahead_axes or [])},
            )
            return validated, notes
        except Exception as exc:
            notes.append(f"Peer structured response invalid ({type(exc).__name__}): {exc}")
            logger.info("peer_react_session_end", extra={**log_extra, "outcome": "validate_error"})
            return None, notes

    notes.append(f"Unexpected structured_response type: {type(sr).__name__}")
    logger.info("peer_react_session_end", extra={**log_extra, "outcome": "unexpected_sr_type"})
    return None, notes


def format_peer_entry_for_brief(entry: dict[str, Any]) -> str:
    """Stable JSON string of the competitor_landscape row for the peer-only brief."""
    try:
        return json.dumps(entry, indent=2, ensure_ascii=False)[:12_000]
    except (TypeError, ValueError):
        return str(entry)[:12_000]
