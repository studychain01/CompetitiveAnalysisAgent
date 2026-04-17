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

    mandatory_news: list[str] = []
    if newsapi_enabled:
        mandatory_news = [
            "",
            "## Mandatory tool use (this run)",
            "The **`news_search`** tool is **enabled** (NewsAPI key configured). You **must** call "
            "`news_search` **at least once** before you produce the final structured competitors "
            "(e.g. query combining the target company name + “competitors”, “vs”, or industry terms). "
            "Still use `tavily_search` for web corroboration when helpful.",
        ]

    return "\n".join(
        [
            "## Research task",
            "Discover **3–6 competitors** of the **target** company described below. "
            "Use tools where enabled. Map each competitor to **home SEC Item 1A risk themes** "
            "from the packed context (see system prompt for mapping rules).",
            "",
            "## Enabled backends (this run)",
            f"- Tavily `tavily_search`: {_on(tavily_enabled)}",
            f"- NewsAPI `news_search`: {_on(newsapi_enabled)}",
            f"- Firecrawl `scrape_url`: {_on(firecrawl_enabled)}",
            *mandatory_news,
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
    async def tavily_search(query: str, max_results: int = 6) -> str:
        """Search the public web for competitors, market maps, analyst comparisons, or company facts."""
        bounded = max(1, min(int(max_results), 10))
        try:
            payload = await tavily.search(query, max_results=bounded)
        except Exception as exc:
            logger.warning("competitor_react_tavily_tool_error", extra={"error": str(exc)})
            return f"Tavily error ({type(exc).__name__}): {exc}"
        return _clip(_format_tavily_block(payload), max_ctx)

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
