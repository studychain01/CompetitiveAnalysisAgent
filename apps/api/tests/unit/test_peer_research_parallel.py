from __future__ import annotations

import pytest

from battlescope_api.graph.nodes.peer_research_parallel import peer_research_parallel_node
from battlescope_api.graph.state import GraphState
from battlescope_api.models.peer_research_digest import (
    AheadAxis,
    PeerResearchDigestLlm,
    PowerUserHypothesis,
)
from battlescope_api.settings import get_settings

_FAKE_OPENAI_KEY = "sk-proj-0123456789abcdefghijklmnopqrstuvwxyzABCDEFGH"


@pytest.fixture
def clear_settings_cache():
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.mark.asyncio
async def test_peer_research_skipped_no_openai(
    monkeypatch: pytest.MonkeyPatch, clear_settings_cache
) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "")
    monkeypatch.setenv("TAVILY_API_KEY", "tvly-test")
    get_settings.cache_clear()

    state: GraphState = {
        "run_id": "r1",
        "thread_id": "t1",
        "competitor_landscape": {
            "status": "ok",
            "competitors": [{"display_name": "PeerCo", "confidence": 0.8}],
        },
        "company_profile": {"name": "HomeCo"},
        "sec_risk_dossier": {},
        "planner_notes": [],
        "trace_events": [],
    }
    out = await peer_research_parallel_node(state)
    dig = out.get("peer_research_digests") or {}
    assert dig.get("status") == "skipped"
    assert dig.get("by_peer") == {}


@pytest.mark.asyncio
async def test_peer_research_skipped_no_search_keys(
    monkeypatch: pytest.MonkeyPatch, clear_settings_cache
) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", _FAKE_OPENAI_KEY)
    monkeypatch.setenv("TAVILY_API_KEY", "")
    monkeypatch.setenv("NEWSAPI_API_KEY", "")
    get_settings.cache_clear()

    state: GraphState = {
        "run_id": "r1",
        "thread_id": "t1",
        "competitor_landscape": {"status": "ok", "competitors": [{"display_name": "PeerCo", "confidence": 0.8}]},
        "planner_notes": [],
        "trace_events": [],
    }
    out = await peer_research_parallel_node(state)
    dig = out.get("peer_research_digests") or {}
    assert dig.get("status") == "skipped"


@pytest.mark.asyncio
async def test_peer_research_mocked_three_parallel(
    monkeypatch: pytest.MonkeyPatch, clear_settings_cache
) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", _FAKE_OPENAI_KEY)
    monkeypatch.setenv("TAVILY_API_KEY", "tvly-test")
    get_settings.cache_clear()

    async def _fake_peer_react(**_kwargs: object) -> tuple[PeerResearchDigestLlm | None, list[str]]:
        return (
            PeerResearchDigestLlm(
                peer_display_name="stub-peer",
                ahead_axes=[
                    AheadAxis(
                        axis="ecosystem",
                        rationale="Stub rationale with evidence gap.",
                        source_urls=["https://example.com/article"],
                        confidence=0.55,
                    )
                ],
                power_user_hypothesis=PowerUserHypothesis(
                    segment_label="Mid-market ops",
                    jobs_to_be_done=["Automate reporting"],
                    signals=["Pricing page lists enterprise tier"],
                ),
                evidence_notes="stub",
                overall_confidence=0.55,
            ),
            [],
        )

    monkeypatch.setattr(
        "battlescope_api.graph.nodes.peer_research_parallel.run_peer_react_research",
        _fake_peer_react,
    )

    state: GraphState = {
        "run_id": "r1",
        "thread_id": "t1",
        "company_name": "HomeCo",
        "company_profile": {"name": "HomeCo", "summary": "We do widgets."},
        "sec_risk_dossier": {"risk_theme_bullets": ["Competition."]},
        "competitor_landscape": {
            "status": "ok",
            "competitors": [
                {"display_name": "AlphaCo", "ticker": "ALP", "confidence": 0.9},
                {"display_name": "BetaCo", "confidence": 0.7},
                {"display_name": "GammaCo", "confidence": 0.6},
            ],
        },
        "planner_notes": [],
        "trace_events": [],
    }
    out = await peer_research_parallel_node(state)
    dig = out.get("peer_research_digests") or {}
    assert dig.get("status") == "ok"
    by_peer = dig.get("by_peer") or {}
    assert len(by_peer) == 3
    assert "ALP" in by_peer
    for _k, row in by_peer.items():
        assert row.get("status") == "ok"
        assert row.get("digest") is not None
    events = out.get("trace_events") or []
    assert any(e.get("message") == "PeerResearchParallel" for e in events)
