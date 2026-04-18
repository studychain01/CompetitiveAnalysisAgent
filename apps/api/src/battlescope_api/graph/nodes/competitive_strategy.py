"""
Terminal synthesis: competitive strategy from profile, SEC themes, competitor landscape, peer digests.
Primary path: single structured LLM. Optional two-phase Tavily follow-up when settings.strategy_allow_tavily_followup.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from langchain_core.messages import HumanMessage
from langchain_openai import ChatOpenAI

from battlescope_api.graph.state import GraphState
from battlescope_api.models.competitive_strategy import (
    CompetitiveStrategyLlm,
    InputQuality,
    StrategyFollowupPrecursor,
    empty_competitive_strategy,
    wrap_strategy_result,
)
from battlescope_api.services.trace import append_trace_event
from battlescope_api.settings import Settings, get_settings
from battlescope_api.tools.http_client import create_http_client
from battlescope_api.tools.tavily_client import TavilyClient
from battlescope_api.tools.tool_client import ToolClient

logger = logging.getLogger(__name__)

_PROMPTS_DIR = Path(__file__).resolve().parents[2] / "prompts"


def _load_system_prompt() -> str:
    return (_PROMPTS_DIR / "competitive_strategy_system.md").read_text(encoding="utf-8")


def _clip(s: str, max_chars: int) -> str:
    s = (s or "").strip()
    if len(s) <= max_chars:
        return s
    return s[: max_chars - 24] + "\n...[truncated]..."


def _format_tavily_snippets(payload: dict[str, Any], *, max_chars: int) -> str:
    lines: list[str] = []
    for idx, item in enumerate(payload.get("results") or [], start=1):
        title = item.get("title") or ""
        url = item.get("url") or ""
        content = (item.get("content") or "").strip()
        lines.append(f"{idx}. {title}\n   URL: {url}\n   Snippet: {content[:600]}")
    text = "\n\n".join(lines) if lines else "(no results)"
    return _clip(text, max_chars)


def _pack_strategy_context(state: GraphState, settings: Settings) -> str:
    max_chars = settings.strategy_context_max_chars
    profile = state.get("company_profile") or {}
    dossier = state.get("sec_risk_dossier") or {}
    landscape = state.get("competitor_landscape") or {}
    digests = state.get("peer_research_digests") or {}

    lines: list[str] = []
    lines.append("## Target identifiers")
    lines.append(f"- company_name: {state.get('company_name') or ''}")
    lines.append(f"- company_url: {state.get('company_url') or ''}")
    lines.append("")
    lines.append("## company_profile (JSON subset)")
    subset = {
        "name": profile.get("name"),
        "summary": profile.get("summary"),
        "uncertainties": profile.get("uncertainties"),
        "earnings_call": profile.get("earnings_call"),
        "category": profile.get("category"),
        "business_model": profile.get("business_model"),
    }
    lines.append(_clip(json.dumps(subset, indent=2, ensure_ascii=False), max_chars // 3))
    lines.append("")
    lines.append("## sec_risk_dossier")
    lines.append(f"- status: {dossier.get('status')!r}")
    lines.append(f"- reason: {dossier.get('reason')!r}")
    bullets = dossier.get("risk_theme_bullets") or []
    if isinstance(bullets, list):
        lines.append("- risk_theme_bullets:")
        for i, b in enumerate(bullets[:14]):
            lines.append(f"  [{i}] {_clip(str(b), 500)}")
    lines.append("")
    lines.append("## competitor_landscape")
    lines.append(_clip(json.dumps(landscape, ensure_ascii=False), max_chars // 3))
    lines.append("")
    lines.append("## peer_research_digests")
    lines.append(_clip(json.dumps(digests, ensure_ascii=False), max_chars // 3))
    by_peer = digests.get("by_peer") if isinstance(digests, dict) else {}
    deep_names: list[str] = []
    if isinstance(by_peer, dict):
        for key, row in by_peer.items():
            if not isinstance(row, dict) or row.get("status") != "ok":
                continue
            digest = row.get("digest") if isinstance(row.get("digest"), dict) else {}
            display = (digest or {}).get("peer_display_name") if isinstance(digest, dict) else ""
            label = str(display).strip() or str(key).strip()
            if label and label not in deep_names:
                deep_names.append(label)
            if len(deep_names) >= 3:
                break
    lines.append("")
    lines.append("## deep_research_peer_names (ordered; max 3)")
    lines.append(json.dumps(deep_names, ensure_ascii=False))
    lines.append(
        "Emit `peer_deep_dives` in this order when possible—one object per name; "
        "if a digest failed, omit that peer or shorten with lower confidence."
    )
    return _clip("\n".join(lines), max_chars)


def _derive_input_quality(landscape: dict[str, Any], digests: dict[str, Any]) -> dict[str, Any]:
    comps = landscape.get("competitors") or []
    n_comp = len(comps) if isinstance(comps, list) else 0
    degraded = bool(landscape.get("degraded")) or str(landscape.get("status") or "") in (
        "partial",
        "empty",
    )
    by_peer = digests.get("by_peer") or {}
    n_rows = len(by_peer) if isinstance(by_peer, dict) else 0
    ok = 0
    if isinstance(by_peer, dict):
        for row in by_peer.values():
            if isinstance(row, dict) and row.get("status") == "ok":
                ok += 1
    notes: list[str] = []
    if degraded or n_comp < 3:
        notes.append("Competitor set incomplete or degraded; strategy is directional only.")
    if n_rows == 0:
        notes.append("No peer deep-digests; rely on competitor_landscape and profile only.")
    elif ok < n_rows:
        notes.append("Some peer digest runs failed or lacked structured output.")
    return {
        "competitor_landscape_degraded": degraded or n_comp < 3,
        "competitor_count": n_comp,
        "peer_digest_rows": n_rows,
        "peer_digests_ok_count": ok,
        "notes": " ".join(notes).strip(),
    }


async def _run_tavily_followup_snippets(
    settings: Settings,
    *,
    packed_context: str,
) -> str:
    """At most 2 Tavily searches from precursor queries; returns markdown block or empty."""
    if not settings.openai_api_key:
        return ""
    model = ChatOpenAI(
        api_key=settings.openai_api_key,
        base_url=settings.openai_sdk_base_url,
        model=settings.openai_model,
        temperature=0.1,
    )
    structured = model.with_structured_output(StrategyFollowupPrecursor)
    msg = HumanMessage(
        content=(
            _load_system_prompt()
            + "\n\n## Task (phase 1 only)\n"
            "From the packed research context below, emit **only** `StrategyFollowupPrecursor`: "
            "up to **2** `followup_queries` for Tavily if a **specific factual gap** remains "
            "(e.g. recent pricing move, market share claim). If context is enough, return **empty** "
            "`followup_queries`. Also list brief `uncertainties`.\n\n"
            "## Packed context\n\n"
            + packed_context
        )
    )
    try:
        pre = await structured.ainvoke([msg])
        if not isinstance(pre, StrategyFollowupPrecursor):
            if isinstance(pre, dict):
                pre = StrategyFollowupPrecursor.model_validate(pre)
            else:
                return ""
    except Exception as exc:
        logger.warning("strategy_followup_precursor_failed", extra={"error": str(exc)})
        return ""

    queries = [str(q).strip() for q in (pre.followup_queries or []) if str(q).strip()][:2]
    if not queries or not settings.tavily_api_key:
        return ""

    parts: list[str] = []
    async with create_http_client() as raw_client:
        tool = ToolClient(
            raw_client,
            max_retries=settings.http_max_retries,
            backoff_base_s=settings.http_backoff_base_s,
            retryable_methods=frozenset({"GET", "POST"}),
        )
        tavily = TavilyClient(settings.tavily_api_key, tool)
        for q in queries:
            try:
                payload = await tavily.search(q, max_results=5)
                parts.append(f"### Query: {q}\n{_format_tavily_snippets(payload, max_chars=8000)}")
            except Exception as exc:
                parts.append(f"### Query: {q}\n(Tavily error: {type(exc).__name__}: {exc})")
    return "\n\n".join(parts)


async def _synthesize_final_strategy(
    settings: Settings,
    *,
    packed_context: str,
    tavily_addendum: str,
) -> CompetitiveStrategyLlm | None:
    if not settings.openai_api_key:
        return None
    model = ChatOpenAI(
        api_key=settings.openai_api_key,
        base_url=settings.openai_sdk_base_url,
        model=settings.openai_model,
        temperature=0.15,
    )
    structured = model.with_structured_output(CompetitiveStrategyLlm)
    addendum_block = (
        "\n\n## Optional live search snippets (may be empty)\n" + tavily_addendum
        if tavily_addendum.strip()
        else ""
    )
    msg = HumanMessage(
        content=(
            _load_system_prompt()
            + "\n\n## Task (final)\n"
            "Produce the full **CompetitiveStrategyLlm** from the packed context below. "
            "Incorporate live snippets only when they clarify a gap; otherwise rely on the pack.\n\n"
            "## Packed context\n\n"
            + packed_context
            + addendum_block
        )
    )
    try:
        out = await structured.ainvoke([msg])
        if isinstance(out, CompetitiveStrategyLlm):
            return out
        if isinstance(out, dict):
            return CompetitiveStrategyLlm.model_validate(out)
    except Exception as exc:
        logger.warning("competitive_strategy_llm_failed", extra={"error": str(exc)})
        return None
    return None


async def competitive_strategy_node(state: GraphState) -> GraphState:
    run_id = state.get("run_id", "")
    events = list(state.get("trace_events", []))
    notes = list(state.get("planner_notes", []))

    append_trace_event(events, "node_start", run_id, "CompetitiveStrategy")

    settings = get_settings()
    if not settings.openai_api_key:
        append_trace_event(events, "node_end", run_id, "CompetitiveStrategy")
        return {
            "competitive_strategy": empty_competitive_strategy(
                status="skipped",
                reason="OPENAI_API_KEY not configured.",
            ),
            "planner_notes": notes + ["CompetitiveStrategy skipped: OPENAI_API_KEY missing."],
            "trace_events": events,
            "stage": "competitive_strategy",
        }

    packed = _pack_strategy_context(state, settings)
    landscape = state.get("competitor_landscape") or {}
    digests = state.get("peer_research_digests") or {}
    iq = _derive_input_quality(landscape if isinstance(landscape, dict) else {}, digests if isinstance(digests, dict) else {})

    tavily_addendum = ""
    if settings.strategy_allow_tavily_followup and settings.tavily_api_key:
        try:
            tavily_addendum = await _run_tavily_followup_snippets(settings, packed_context=packed)
            if tavily_addendum.strip():
                notes.append("CompetitiveStrategy: ran optional Tavily follow-up (≤2 queries).")
        except Exception as exc:
            logger.warning("strategy_tavily_followup_block_failed", extra={"error": str(exc)})
            notes.append(f"CompetitiveStrategy: Tavily follow-up skipped ({type(exc).__name__}).")

    try:
        model = await _synthesize_final_strategy(settings, packed_context=packed, tavily_addendum=tavily_addendum)
    except Exception as exc:
        logger.exception("competitive_strategy_node_failed")
        append_trace_event(events, "node_end", run_id, "CompetitiveStrategy")
        return {
            "competitive_strategy": empty_competitive_strategy(
                status="error",
                reason=f"{type(exc).__name__}: {exc}",
            ),
            "planner_notes": notes + [f"CompetitiveStrategy failed: {exc}"],
            "trace_events": events,
            "stage": "competitive_strategy",
        }

    if model is None:
        append_trace_event(events, "node_end", run_id, "CompetitiveStrategy")
        return {
            "competitive_strategy": empty_competitive_strategy(
                status="error",
                reason="LLM returned no structured strategy.",
            ),
            "planner_notes": notes + ["CompetitiveStrategy: no structured output from model."],
            "trace_events": events,
            "stage": "competitive_strategy",
        }

    prior_notes = (model.input_quality.notes or "").strip()
    extra_notes = (iq.get("notes") or "").strip()
    merged_notes = f"{prior_notes} {extra_notes}".strip() if extra_notes else prior_notes
    merged_iq = {
        "competitor_landscape_degraded": bool(iq.get("competitor_landscape_degraded")),
        "competitor_count": int(iq.get("competitor_count") or 0),
        "peer_digest_rows": int(iq.get("peer_digest_rows") or 0),
        "peer_digests_ok_count": int(iq.get("peer_digests_ok_count") or 0),
        "notes": merged_notes,
    }
    model = model.model_copy(update={"input_quality": InputQuality.model_validate(merged_iq)})

    overall_status = "ok"
    reason = None
    if merged_iq["competitor_landscape_degraded"] or merged_iq["competitor_count"] < 3:
        overall_status = "partial"
        reason = "Upstream competitor set incomplete or degraded; validate before execution."

    payload = wrap_strategy_result(model, status=overall_status, reason=reason)
    notes.append(f"CompetitiveStrategy: emitted strategy ({overall_status}).")

    append_trace_event(events, "node_end", run_id, "CompetitiveStrategy")
    return {
        "competitive_strategy": payload,
        "planner_notes": notes,
        "trace_events": events,
        "stage": "competitive_strategy",
    }


async def run_competitive_strategy_for_tests(state: GraphState) -> GraphState:
    return await competitive_strategy_node(state)
