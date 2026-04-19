"""
Run up to three bounded peer-deep ReAct sessions in parallel (asyncio.gather), one session per competitor.
"""

from __future__ import annotations

import asyncio
import logging
import re
from typing import Any

from battlescope_api.graph.nodes.peer_react_agent import (
    build_peer_react_user_brief,
    format_peer_entry_for_brief,
    run_peer_react_research,
)
from battlescope_api.graph.state import GraphState
from battlescope_api.models.peer_research_digest import empty_peer_research_payload
from battlescope_api.services.trace import append_trace_event
from battlescope_api.settings import get_settings
from battlescope_api.tools.alphavantage_client import AlphaVantageClient
from battlescope_api.tools.firecrawl_client import FirecrawlClient
from battlescope_api.tools.http_client import create_http_client
from battlescope_api.tools.newsapi_client import NewsApiClient
from battlescope_api.tools.tavily_client import TavilyClient
from battlescope_api.tools.tool_client import ToolClient

logger = logging.getLogger(__name__)


def _slug(name: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "_", (name or "").lower()).strip("_")
    return s or "unknown"


def _base_peer_key(entry: dict[str, Any]) -> str:
    raw_t = entry.get("ticker")
    if isinstance(raw_t, str) and raw_t.strip():
        return raw_t.strip().upper()
    return _slug(str(entry.get("display_name") or ""))


def _assign_unique_peer_keys(peers: list[dict[str, Any]]) -> list[tuple[str, dict[str, Any]]]:
    used: set[str] = set()
    out: list[tuple[str, dict[str, Any]]] = []
    for p in peers:
        base = _base_peer_key(p)
        k = base
        n = 2
        while k in used:
            k = f"{base}_{n}"
            n += 1
        used.add(k)
        out.append((k, p))
    return out


def _select_top_peers(landscape: dict[str, Any], *, max_peers: int = 3) -> list[dict[str, Any]]:
    """
    Deterministic: competitors with non-empty display_name, sorted by confidence descending.
    """
    comps = landscape.get("competitors") or []
    if not isinstance(comps, list):
        return []
    rows: list[dict[str, Any]] = [
        c for c in comps if isinstance(c, dict) and str(c.get("display_name") or "").strip()
    ]
    rows.sort(key=lambda c: float(c.get("confidence") or 0.0), reverse=True)
    return rows[:max_peers]


def _clip(s: str, max_chars: int) -> str:
    s = (s or "").strip()
    if len(s) <= max_chars:
        return s
    return s[: max_chars - 20] + "\n...[truncated]..."


async def peer_research_parallel_node(state: GraphState) -> GraphState:
    run_id = state.get("run_id", "")
    events = list(state.get("trace_events", []))
    notes = list(state.get("planner_notes", []))

    append_trace_event(events, "node_start", run_id, "PeerResearchParallel")

    settings = get_settings()
    landscape = state.get("competitor_landscape") or {}
    profile = state.get("company_profile") or {}
    dossier = state.get("sec_risk_dossier") or {}

    if not settings.openai_api_key:
        append_trace_event(events, "node_end", run_id, "PeerResearchParallel")
        return {
            "peer_research_digests": empty_peer_research_payload(
                status="skipped",
                reason="OPENAI_API_KEY not configured.",
            ),
            "planner_notes": notes + ["PeerResearchParallel skipped: OPENAI_API_KEY missing."],
            "trace_events": events,
            "stage": "peer_research_parallel",
        }

    if not settings.tavily_api_key and not settings.newsapi_api_key:
        append_trace_event(events, "node_end", run_id, "PeerResearchParallel")
        return {
            "peer_research_digests": empty_peer_research_payload(
                status="skipped",
                reason="Neither TAVILY_API_KEY nor NEWSAPI_API_KEY configured.",
            ),
            "planner_notes": notes
            + ["PeerResearchParallel skipped: need Tavily or NewsAPI for grounded peer research."],
            "trace_events": events,
            "stage": "peer_research_parallel",
        }

    peers = _select_top_peers(landscape if isinstance(landscape, dict) else {})
    if not peers:
        append_trace_event(events, "node_end", run_id, "PeerResearchParallel")
        return {
            "peer_research_digests": empty_peer_research_payload(
                status="skipped",
                reason="No competitors in competitor_landscape to research.",
            ),
            "planner_notes": notes + ["PeerResearchParallel skipped: empty competitor_landscape."],
            "trace_events": events,
            "stage": "peer_research_parallel",
        }

    home_name = str(
        state.get("company_name") or profile.get("name") or "",
    ).strip()
    summary = _clip(str(profile.get("summary") or ""), 8_000)
    bullets = dossier.get("risk_theme_bullets") or []
    if isinstance(bullets, list):
        sec_text = "\n".join(f"- {str(b).strip()}" for b in bullets[:14] if str(b).strip())
    else:
        sec_text = ""
    sec_clip = _clip(sec_text, 8_000)

    news_on = bool(settings.newsapi_api_key)
    tav_on = bool(settings.tavily_api_key)
    fc_on = bool(settings.firecrawl_api_key)
    av_on = bool(settings.alphavantage_api_key)

    keyed_peers = _assign_unique_peer_keys(peers)
    logger.info(
        "peer_research_parallel_start",
        extra={
            "run_id": run_id,
            "peer_count": len(keyed_peers),
            "peer_keys": [k for k, _ in keyed_peers],
            "peer_names": [str(p.get("display_name") or "") for _, p in keyed_peers],
        },
    )

    async def _one_peer(key: str, peer: dict[str, Any]) -> tuple[str, dict[str, Any]]:
        brief = build_peer_react_user_brief(
            peer_display_name=str(peer.get("display_name") or "").strip(),
            peer_ticker=(str(peer.get("ticker")).strip().upper() if peer.get("ticker") else None),
            peer_landscape_json=format_peer_entry_for_brief(peer),
            home_company_name=home_name,
            home_summary_clip=summary,
            home_sec_bullets_clip=sec_clip,
            tavily_enabled=tav_on,
            newsapi_enabled=news_on,
            firecrawl_enabled=fc_on,
            alphavantage_enabled=av_on,
        )
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
                alphavantage = AlphaVantageClient(settings.alphavantage_api_key, http_tool)
                sr, react_notes = await run_peer_react_research(
                    settings=settings,
                    tavily=tavily,
                    newsapi=newsapi,
                    firecrawl=firecrawl,
                    alphavantage=alphavantage,
                    human_brief=brief,
                    peer_key=key,
                    peer_display_name=str(peer.get("display_name") or "").strip() or None,
                )
        except Exception as exc:
            logger.exception("peer_research_single_peer_failed", extra={"peer_key": key})
            return key, {
                "status": "error",
                "display_name": peer.get("display_name"),
                "ticker": peer.get("ticker"),
                "digest": None,
                "notes": [f"{type(exc).__name__}: {exc}"],
            }

        st = "ok" if sr is not None else "error"
        return key, {
            "status": st,
            "display_name": peer.get("display_name"),
            "ticker": peer.get("ticker"),
            "digest": sr.model_dump() if sr else None,
            "notes": react_notes,
        }

    raw_results = await asyncio.gather(
        *[_one_peer(k, p) for k, p in keyed_peers],
        return_exceptions=True,
    )

    by_peer: dict[str, Any] = {}
    for idx, r in enumerate(raw_results):
        key, peer_row = keyed_peers[idx]
        if isinstance(r, Exception):
            by_peer[key] = {
                "status": "error",
                "display_name": peer_row.get("display_name"),
                "ticker": peer_row.get("ticker"),
                "digest": None,
                "notes": [f"{type(r).__name__}: {r}"],
            }
            continue
        k2, payload = r
        by_peer[k2] = payload

    for pk, row in by_peer.items():
        append_trace_event(
            events,
            "peer_worker_done",
            run_id,
            pk,
            {
                "display_name": row.get("display_name"),
                "status": row.get("status"),
                "digest_peer_field": (row.get("digest") or {}).get("peer_display_name")
                if isinstance(row.get("digest"), dict)
                else None,
            },
        )

    ok_count = sum(1 for v in by_peer.values() if v.get("status") == "ok")
    n_peers = len(keyed_peers)
    if ok_count == n_peers:
        overall = "ok"
        reason = None
    elif ok_count > 0:
        overall = "partial"
        reason = f"{ok_count}/{n_peers} peer digests succeeded."
    else:
        overall = "error"
        reason = "All peer research runs failed or returned no structured digest."

    payload_out = {
        "status": overall,
        "reason": reason,
        "by_peer": by_peer,
    }

    notes.append(
        f"PeerResearchParallel: {ok_count}/{n_peers} peer(s) completed with structured digest."
    )

    append_trace_event(events, "node_end", run_id, "PeerResearchParallel")
    return {
        "peer_research_digests": payload_out,
        "planner_notes": notes,
        "trace_events": events,
        "stage": "peer_research_parallel",
    }


async def run_peer_research_parallel_for_tests(state: GraphState) -> GraphState:
    return await peer_research_parallel_node(state)
