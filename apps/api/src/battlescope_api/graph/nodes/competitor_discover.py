"""
Post-SEC competitor discovery: bounded ReAct over intake profile + Item 1A theme bullets.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from battlescope_api.graph.nodes.competitor_react_agent import (
    build_competitor_react_user_brief,
    run_competitor_react_research,
)
from battlescope_api.graph.state import GraphState
from battlescope_api.models.competitor_landscape import (
    CompetitorLandscapeLlm,
    empty_competitor_landscape,
    finalize_landscape_from_llm,
)
from battlescope_api.services.trace import append_trace_event
from battlescope_api.settings import get_settings
from battlescope_api.tools.firecrawl_client import FirecrawlClient
from battlescope_api.tools.http_client import create_http_client
from battlescope_api.tools.newsapi_client import NewsApiClient
from battlescope_api.tools.tavily_client import TavilyClient
from battlescope_api.tools.tool_client import ToolClient

logger = logging.getLogger(__name__)


def _clip(s: str, max_chars: int) -> str:
    s = (s or "").strip()
    if len(s) <= max_chars:
        return s
    return s[: max_chars - 20] + "\n...[truncated]..."


def _pack_competitor_context(
    *,
    company_name: str,
    company_url: str,
    profile: dict[str, Any],
    dossier: dict[str, Any],
    max_chars: int,
) -> str:
    lines: list[str] = []
    lines.append("### Canonical profile fields")
    lines.append(f"- profile.name: {_clip(str(profile.get('name') or ''), 200)}")
    lines.append(f"- profile.summary:\n{_clip(str(profile.get('summary') or ''), min(6000, max_chars // 2))}")
    unc = profile.get("uncertainties") or []
    if isinstance(unc, list) and unc:
        lines.append("- profile.uncertainties:")
        for u in unc[:12]:
            lines.append(f"  - {_clip(str(u), 240)}")
    ec = profile.get("earnings_call")
    if isinstance(ec, dict):
        lines.append("### earnings_call (intake / call-derived bullets)")
        lines.append(f"- symbol (do not list this company as a competitor): {ec.get('symbol')!r}")
        lines.append(f"- quarter: {ec.get('quarter')!r}")
        for key in ("strengths", "weaknesses"):
            xs = ec.get(key) or []
            if isinstance(xs, list) and xs:
                lines.append(f"- {key}:")
                for b in xs[:12]:
                    lines.append(f"  - {_clip(str(b), 320)}")
    lines.append("### 10-K Item 1A distilled themes (home company)")
    lines.append(f"- sec_risk_dossier.status: {dossier.get('status')!r}")
    if dossier.get("reason"):
        lines.append(f"- sec_risk_dossier.reason: {_clip(str(dossier.get('reason')), 400)}")
    ext = dossier.get("extraction")
    if isinstance(ext, dict):
        lines.append(f"- extraction (JSON): {json.dumps(ext, default=str)[:1200]}")
    bullets = dossier.get("risk_theme_bullets") or []
    if isinstance(bullets, list) and bullets:
        lines.append("- risk_theme_bullets (indexed from 0):")
        for i, b in enumerate(bullets[:14]):
            lines.append(f"  [{i}] {_clip(str(b), 500)}")
    elif str(dossier.get("status") or "") != "ok":
        lines.append("- risk_theme_bullets: (none — SEC step did not produce themes)")
    text = "\n".join(lines)
    return _clip(text, max_chars)


async def competitor_discover_node(state: GraphState) -> GraphState:
    run_id = state.get("run_id", "")
    events = list(state.get("trace_events", []))
    notes = list(state.get("planner_notes", []))

    append_trace_event(events, "node_start", run_id, "CompetitorDiscover")

    settings = get_settings()
    profile = state.get("company_profile") or {}
    dossier = state.get("sec_risk_dossier") or {}
    company_name = str(state.get("company_name") or profile.get("name") or "").strip()
    company_url = str(state.get("company_url") or "").strip()

    if not settings.openai_api_key:
        append_trace_event(events, "node_end", run_id, "CompetitorDiscover")
        return {
            "competitor_landscape": empty_competitor_landscape(
                status="skipped",
                reason="OPENAI_API_KEY not configured.",
            ),
            "planner_notes": notes + ["CompetitorDiscover skipped: OPENAI_API_KEY missing."],
            "trace_events": events,
            "stage": "competitor_discover",
        }

    if not settings.tavily_api_key and not settings.newsapi_api_key:
        append_trace_event(events, "node_end", run_id, "CompetitorDiscover")
        return {
            "competitor_landscape": empty_competitor_landscape(
                status="skipped",
                reason="Neither TAVILY_API_KEY nor NEWSAPI_API_KEY configured; external search disabled.",
            ),
            "planner_notes": notes
            + ["CompetitorDiscover skipped: need at least one of Tavily or NewsAPI for grounded peer search."],
            "trace_events": events,
            "stage": "competitor_discover",
        }

    packed = _pack_competitor_context(
        company_name=company_name,
        company_url=company_url,
        profile=profile if isinstance(profile, dict) else {},
        dossier=dossier if isinstance(dossier, dict) else {},
        max_chars=min(24_000, settings.competitor_context_max_chars * 3),
    )
    newsapi_on = bool(settings.newsapi_api_key)
    logger.info(
        "competitor_discover_tooling",
        extra={
            "tavily_configured": bool(settings.tavily_api_key),
            "newsapi_configured": newsapi_on,
            "firecrawl_configured": bool(settings.firecrawl_api_key),
        },
    )

    brief = build_competitor_react_user_brief(
        company_name=company_name,
        company_url=company_url,
        tavily_enabled=bool(settings.tavily_api_key),
        newsapi_enabled=newsapi_on,
        firecrawl_enabled=bool(settings.firecrawl_api_key),
        packed_context=packed,
    )

    landscape: dict[str, Any]
    try:
        async with create_http_client() as raw_client:
            http_tool = ToolClient(
                raw_client,
                max_retries=settings.http_max_retries,
                backoff_base_s=settings.http_backoff_base_s,
                retryable_methods=frozenset({"GET", "POST"}),
            )
            tavily = TavilyClient(settings.tavily_api_key, http_tool)
            newsapi = NewsApiClient(settings.newsapi_api_key, http_tool)
            firecrawl = FirecrawlClient(settings.firecrawl_api_key, http_tool)
            sr, react_notes = await run_competitor_react_research(
                settings=settings,
                tavily=tavily,
                newsapi=newsapi,
                firecrawl=firecrawl,
                human_brief=brief,
            )
    except Exception as exc:
        logger.exception("competitor_discover_pipeline_failed")
        notes.append(f"CompetitorDiscover failed ({type(exc).__name__}): {exc}")
        landscape = empty_competitor_landscape(status="error", reason=str(exc))
        append_trace_event(events, "node_end", run_id, "CompetitorDiscover")
        return {
            "competitor_landscape": landscape,
            "planner_notes": notes,
            "trace_events": events,
            "stage": "competitor_discover",
        }

    notes.extend(react_notes)
    if sr is None:
        reason = react_notes[0] if react_notes else "No structured competitor output."
        landscape = empty_competitor_landscape(status="error", reason=reason)
        notes.append("CompetitorDiscover: no structured landscape produced.")
    else:
        landscape = finalize_landscape_from_llm(sr)
        n = len(landscape.get("competitors") or [])
        if landscape.get("degraded"):
            notes.append(f"CompetitorDiscover: partial — only {n} peer(s) after dedupe (target 3–6).")
        else:
            notes.append(f"CompetitorDiscover: produced {n} competitor row(s).")

    append_trace_event(events, "node_end", run_id, "CompetitorDiscover")
    return {
        "competitor_landscape": landscape,
        "planner_notes": notes,
        "trace_events": events,
        "stage": "competitor_discover",
    }


async def run_competitor_discover_for_tests(state: GraphState) -> GraphState:
    """Test entrypoint mirroring ``competitor_discover_node``."""
    return await competitor_discover_node(state)
