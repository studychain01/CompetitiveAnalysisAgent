from __future__ import annotations

import pytest

from battlescope_api.graph.nodes.competitive_strategy import competitive_strategy_node
from battlescope_api.graph.state import GraphState
from battlescope_api.models.competitive_strategy import (
    CompetitiveStrategyLlm,
    HorizonPlan,
    PrioritizedMove,
)
from battlescope_api.settings import get_settings

_FAKE_OPENAI_KEY = "sk-proj-0123456789abcdefghijklmnopqrstuvwxyzABCDEFGH"


@pytest.fixture
def clear_settings_cache():
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.mark.asyncio
async def test_competitive_strategy_skipped_no_openai(
    monkeypatch: pytest.MonkeyPatch, clear_settings_cache
) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "")
    get_settings.cache_clear()

    state: GraphState = {
        "run_id": "r1",
        "thread_id": "t1",
        "company_profile": {"name": "Co"},
        "competitor_landscape": {"competitors": []},
        "peer_research_digests": {"by_peer": {}},
        "planner_notes": [],
        "trace_events": [],
    }
    out = await competitive_strategy_node(state)
    strat = out.get("competitive_strategy") or {}
    assert strat.get("status") == "skipped"


@pytest.mark.asyncio
async def test_competitive_strategy_mocked_synthesis(
    monkeypatch: pytest.MonkeyPatch, clear_settings_cache
) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", _FAKE_OPENAI_KEY)
    monkeypatch.setenv("STRATEGY_TAVILY_FOLLOWUP", "false")
    get_settings.cache_clear()

    stub = CompetitiveStrategyLlm(
        executive_summary="We focus on integrations.",
        advantage_gap_matrix=[],
        prioritized_moves=[
            PrioritizedMove(
                rank=1,
                title="Ship integration layer",
                rationale="Peers lead on ecosystem.",
                horizon="short",
                effort="low_hanging",
                risk_to_home="Execution",
                owner_hint="product",
            )
        ],
        short_term_plan=HorizonPlan(horizon_label="0–90d", bullets=["Milestone A"]),
        long_term_plan=HorizonPlan(horizon_label="6–24m", bullets=["Platform bet"]),
        low_hanging_fruits=["Partner with one ISV"],
        long_term_targets=["Own workflow category"],
        non_goals=["Price war with leader"],
    )

    async def _fake_synth(*_a: object, **_kw: object) -> CompetitiveStrategyLlm | None:
        return stub

    monkeypatch.setattr(
        "battlescope_api.graph.nodes.competitive_strategy._synthesize_final_strategy",
        _fake_synth,
    )

    state: GraphState = {
        "run_id": "r1",
        "thread_id": "t1",
        "company_name": "HomeCo",
        "company_profile": {"name": "HomeCo", "summary": "B2B SaaS"},
        "sec_risk_dossier": {"status": "ok", "risk_theme_bullets": ["Competition."]},
        "competitor_landscape": {"status": "ok", "degraded": False, "competitors": [{"display_name": "Peer", "confidence": 0.8}]},
        "peer_research_digests": {"status": "ok", "by_peer": {"PEER": {"status": "ok", "digest": {}}}},
        "planner_notes": [],
        "trace_events": [],
    }
    out = await competitive_strategy_node(state)
    strat = out.get("competitive_strategy") or {}
    assert strat.get("status") == "partial"
    assert strat.get("executive_summary") == "We focus on integrations."
    assert strat.get("prioritized_moves")
    events = out.get("trace_events") or []
    assert any(e.get("message") == "CompetitiveStrategy" for e in events)
