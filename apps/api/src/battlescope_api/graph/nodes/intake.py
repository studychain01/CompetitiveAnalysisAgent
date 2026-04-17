from __future__ import annotations

import logging
from urllib.parse import urlparse

import httpx

from battlescope_api.graph.nodes.intake_react_agent import (
    build_intake_user_brief,
    run_intake_react_research,
)
from battlescope_api.graph.state import GraphState
from battlescope_api.services.trace import append_trace_event
from battlescope_api.settings import Settings, get_settings
from battlescope_api.tools.alphavantage_client import AlphaVantageClient
from battlescope_api.tools.firecrawl_client import FirecrawlClient
from battlescope_api.tools.http_client import create_http_client
from battlescope_api.tools.tavily_client import TavilyClient
from battlescope_api.tools.tool_client import ToolClient

logger = logging.getLogger(__name__)


def normalize_company_url(raw: str | None) -> tuple[str | None, str | None]:
    """
    Returns ``(normalized_url, registrable_domain)``.
    ``normalized_url`` includes scheme; domain strips leading ``www.``.
    """
    if raw is None:
        return None, None
    u = raw.strip()
    if not u:
        return None, None
    if not u.startswith(("http://", "https://")):
        u = "https://" + u
    parsed = urlparse(u)
    host = (parsed.hostname or "").lower()
    if not host:
        return None, None
    allowed = frozenset("abcdefghijklmnopqrstuvwxyz0123456789.-")
    if any(ch not in allowed for ch in host):
        return None, None
    domain = host[4:] if host.startswith("www.") else host
    return u, domain


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
        return ""
    data = payload.get("data") or {}
    md = data.get("markdown") or payload.get("markdown") or ""
    return str(md)


def _clip(text: str, max_chars: int) -> str:
    if len(text) <= max_chars:
        return text
    return text[: max_chars - 20] + "\n...[truncated]..."


def _apply_intake_degraded_flag(profile: dict) -> dict:
    conf = float(profile.get("profile_confidence") or 0.0)
    profile["intake_degraded"] = bool(profile.get("intake_degraded")) or conf < 0.45
    return profile


def _heuristic_profile(
    *,
    display_name: str,
    domain: str | None,
    tavily_a: dict,
    tavily_b: dict | None,
    markdown: str,
    settings: Settings,
) -> dict:
    tavily_text = _format_tavily_block(tavily_a)
    if tavily_b:
        tavily_text += "\n\n---\n\n" + _format_tavily_block(tavily_b)
    summary_parts: list[str] = []
    if markdown.strip():
        summary_parts.append("Homepage/markdown excerpt:\n" + _clip(markdown, 4000))
    summary_parts.append("Web snippets:\n" + _clip(tavily_text, settings.intake_context_max_chars))
    summary = "\n\n".join(summary_parts).strip() or f"No web context collected for {display_name}."
    return _apply_intake_degraded_flag(
        {
            "name": display_name,
            "category": "unknown",
            "buyer": "unknown",
            "business_model": "unknown",
            "summary": summary,
            "uncertainties": [
                "LLM not configured or failed; profile assembled from raw snippets/markdown only."
            ],
            "primary_domain": domain,
            "category_alternatives": [],
            "profile_confidence": 0.35,
            "earnings_call": {
                "symbol": None,
                "quarter": None,
                "strengths": [],
                "weaknesses": [],
            },
            "intake_degraded": True,
        }
    )


def _primary_tavily_query(
    *,
    company_name: str,
    display_name: str,
    domain: str | None,
) -> str:
    if company_name:
        return f'"{display_name}" official website product what do they do'
    if domain:
        return f'"{domain}" company product about'
    return f'"{display_name}" company'


async def _gather_snippets_for_heuristic(
    *,
    tavily: TavilyClient,
    firecrawl: FirecrawlClient,
    settings: Settings,
    company_name: str,
    display_name: str,
    domain: str | None,
    url_normalized: str | None,
    planner_notes: list[str],
) -> tuple[dict, dict | None, str, bool]:
    """One broad Tavily pass plus optional Firecrawl for heuristic fallback context."""
    degraded = False
    tavily_main: dict = {"results": []}
    tavily_site: dict | None = None
    markdown = ""
    if not settings.tavily_api_key:
        planner_notes.append("TAVILY_API_KEY missing; intake uses URL/name heuristics only.")
        degraded = True
    else:
        try:
            tavily_main = await tavily.search(
                _primary_tavily_query(
                    company_name=company_name,
                    display_name=display_name,
                    domain=domain,
                ),
                max_results=6,
            )
        except httpx.RequestError as exc:
            logger.warning("intake_tavily_failed", extra={"error": str(exc)})
            planner_notes.append(f"Tavily search failed: {type(exc).__name__}")
            degraded = True
    if url_normalized and settings.firecrawl_api_key:
        try:
            firecrawl_payload = await firecrawl.scrape_url(url_normalized)
            markdown = _firecrawl_markdown(firecrawl_payload)
            if not markdown.strip():
                planner_notes.append("Firecrawl returned empty markdown; falling back to Tavily snippets.")
                degraded = True
        except httpx.RequestError as exc:
            logger.warning("intake_firecrawl_failed", extra={"error": str(exc)})
            planner_notes.append(f"Firecrawl scrape failed: {type(exc).__name__}")
            degraded = True
    elif url_normalized and not settings.firecrawl_api_key:
        planner_notes.append("FIRECRAWL_API_KEY missing; skipping primary-page scrape.")
    if settings.tavily_api_key and not (tavily_main.get("results") or []):
        planner_notes.append("Tavily returned no usable results; profile confidence will be low.")
        degraded = True
    return tavily_main, tavily_site, markdown, degraded


async def intake_node(state: GraphState) -> GraphState:
    """
    IntakeProfiler: bounded ReAct research (Tavily + Firecrawl tools) plus structured profile,
    with heuristics when keys are missing or the agent fails.
    """
    run_id = state.get("run_id", "")
    events = list(state.get("trace_events", []))
    planner_notes = list(state.get("planner_notes", []))

    append_trace_event(events, "node_start", run_id, "IntakeProfiler")

    settings = get_settings()

    company_name = (state.get("company_name") or "").strip()
    company_url = (state.get("company_url") or "").strip() or None

    url_normalized, domain = normalize_company_url(company_url)
    if company_url and not url_normalized:
        planner_notes.append("Provided company_url could not be normalized; treating as name-only context.")

    display_name = company_name or (
        (domain or "").split(".")[0].replace("-", " ").title() if domain else "unknown"
    )

    intake_degraded = False
    profile: dict

    append_trace_event(events, "tool_start", run_id, "intake_research")
    async with create_http_client() as raw_client:
        tool = ToolClient(
            raw_client,
            max_retries=settings.http_max_retries,
            backoff_base_s=settings.http_backoff_base_s,
            retryable_methods=frozenset({"GET", "POST"}),
        )
        tavily = TavilyClient(settings.tavily_api_key, tool)
        firecrawl = FirecrawlClient(settings.firecrawl_api_key, tool)
        alphavantage = AlphaVantageClient(settings.alphavantage_api_key, tool)

        can_react = bool(
            settings.openai_api_key
            and (
                settings.tavily_api_key
                or settings.firecrawl_api_key
                or settings.alphavantage_api_key
            )
        )

        if can_react:
            human_brief = build_intake_user_brief(
                company_name=company_name,
                company_url=company_url,
                url_normalized=url_normalized,
                domain=domain,
                display_name=display_name,
                tavily_enabled=bool(settings.tavily_api_key),
                firecrawl_enabled=bool(settings.firecrawl_api_key),
                alphavantage_enabled=bool(settings.alphavantage_api_key),
            )
            prof_llm, react_notes = await run_intake_react_research(
                settings=settings,
                tavily=tavily,
                firecrawl=firecrawl,
                alphavantage=alphavantage,
                human_brief=human_brief,
            )
            planner_notes.extend(react_notes)
            if prof_llm is not None:
                profile = _apply_intake_degraded_flag(prof_llm.as_state_dict())
                conf = float(profile.get("profile_confidence") or 0.0)
                intake_degraded = bool(profile.get("intake_degraded")) or conf < 0.45
            else:
                t_main, t_site, md, gdeg = await _gather_snippets_for_heuristic(
                    tavily=tavily,
                    firecrawl=firecrawl,
                    settings=settings,
                    company_name=company_name,
                    display_name=display_name,
                    domain=domain,
                    url_normalized=url_normalized,
                    planner_notes=planner_notes,
                )
                intake_degraded = gdeg or True
                profile = _heuristic_profile(
                    display_name=display_name,
                    domain=domain,
                    tavily_a=t_main,
                    tavily_b=t_site,
                    markdown=md,
                    settings=settings,
                )
        elif settings.openai_api_key:
            planner_notes.append(
                "OPENAI_API_KEY is set but no research keys are available "
                "(TAVILY_API_KEY, FIRECRAWL_API_KEY, or ALPHA_VANTAGE_API_KEY); cannot run ReAct intake research."
            )
            profile = _heuristic_profile(
                display_name=display_name,
                domain=domain,
                tavily_a={"results": []},
                tavily_b=None,
                markdown="",
                settings=settings,
            )
            intake_degraded = True
        else:
            t_main, t_site, md, gdeg = await _gather_snippets_for_heuristic(
                tavily=tavily,
                firecrawl=firecrawl,
                settings=settings,
                company_name=company_name,
                display_name=display_name,
                domain=domain,
                url_normalized=url_normalized,
                planner_notes=planner_notes,
            )
            intake_degraded = gdeg
            planner_notes.append("OPENAI_API_KEY missing; using heuristic profile from research context.")
            profile = _heuristic_profile(
                display_name=display_name,
                domain=domain,
                tavily_a=t_main,
                tavily_b=t_site,
                markdown=md,
                settings=settings,
            )
            intake_degraded = True

    append_trace_event(events, "tool_end", run_id, "intake_research")

    if not profile.get("name"):
        profile["name"] = display_name

    if profile.get("category_alternatives") and len(profile["category_alternatives"]) >= 2:
        planner_notes.append("dual-category mode: multiple plausible categories from model output.")

    if intake_degraded:
        profile["intake_degraded"] = True

    append_trace_event(events, "node_end", run_id, "IntakeProfiler")

    return {
        "company_url_normalized": url_normalized,
        "company_profile": profile,
        "planner_notes": planner_notes,
        "stage": "intake",
        "trace_events": events,
    }


async def run_intake_profiler(state: GraphState) -> GraphState:
    """Async entrypoint for tests and notebooks (same behavior as the LangGraph node)."""
    return await intake_node(state)
