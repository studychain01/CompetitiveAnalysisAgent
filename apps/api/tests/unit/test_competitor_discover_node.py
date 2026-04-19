from __future__ import annotations

import pytest

from battlescope_api.graph.nodes.competitor_discover import competitor_discover_node
from battlescope_api.graph.state import GraphState
from battlescope_api.models.competitor_landscape import CompetitorEntry, CompetitorLandscapeLlm, SecConcernDomainRow
from battlescope_api.settings import get_settings

_FAKE_OPENAI_KEY = "sk-proj-0123456789abcdefghijklmnopqrstuvwxyzABCDEFGH"


@pytest.fixture
def clear_settings_cache():
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.mark.asyncio
async def test_competitor_discover_skipped_no_openai(
    monkeypatch: pytest.MonkeyPatch, clear_settings_cache
) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "")
    monkeypatch.setenv("TAVILY_API_KEY", "tvly-test")
    get_settings.cache_clear()

    state: GraphState = {
        "run_id": "r1",
        "thread_id": "t1",
        "company_name": "TargetCo",
        "company_profile": {"name": "TargetCo", "summary": "Does widgets."},
        "sec_risk_dossier": {"status": "skipped", "risk_theme_bullets": []},
        "planner_notes": [],
        "trace_events": [],
    }
    out = await competitor_discover_node(state)
    ls = out.get("competitor_landscape") or {}
    assert ls.get("status") == "skipped"
    assert ls.get("competitors") == []
    assert "OPENAI_API_KEY" in " ".join(out.get("planner_notes", []))


@pytest.mark.asyncio
async def test_competitor_discover_skipped_no_search_keys(
    monkeypatch: pytest.MonkeyPatch, clear_settings_cache
) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", _FAKE_OPENAI_KEY)
    monkeypatch.setenv("TAVILY_API_KEY", "")
    monkeypatch.setenv("NEWSAPI_API_KEY", "")
    get_settings.cache_clear()

    state: GraphState = {
        "run_id": "r1",
        "thread_id": "t1",
        "company_name": "TargetCo",
        "company_profile": {"name": "TargetCo", "summary": "Does widgets."},
        "sec_risk_dossier": {"status": "ok", "risk_theme_bullets": ["Competition may erode margins."]},
        "planner_notes": [],
        "trace_events": [],
    }
    out = await competitor_discover_node(state)
    ls = out.get("competitor_landscape") or {}
    assert ls.get("status") == "skipped"
    assert "Tavily" in " ".join(out.get("planner_notes", [])) or "NewsAPI" in " ".join(
        out.get("planner_notes", [])
    )


@pytest.mark.asyncio
async def test_competitor_discover_mocked_react_three_peers(
    monkeypatch: pytest.MonkeyPatch, clear_settings_cache
) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", _FAKE_OPENAI_KEY)
    monkeypatch.setenv("TAVILY_API_KEY", "tvly-test")
    monkeypatch.setenv("NEWSAPI_API_KEY", "")
    get_settings.cache_clear()

    structured = CompetitorLandscapeLlm(
        target_company_context_note="Used profile + SEC bullets only.",
        competitors=[
            CompetitorEntry(
                display_name="Peer A Inc",
                ticker="PEERA",
                why_in_top_set="Named in industry comparisons with TargetCo.",
                evidence_grade="moderate",
                confidence=0.7,
                sec_concern_domains=[
                    SecConcernDomainRow(
                        home_sec_theme_label="Competitive pricing pressure",
                        home_risk_bullet_index=0,
                        peer_positioning="Often cited as lower-cost alternative in trade press.",
                        supporting_urls=["https://example.com/a"],
                        speculative=False,
                    )
                ],
            ),
            CompetitorEntry(
                display_name="Peer B",
                why_in_top_set="Same buyer and product category.",
                evidence_grade="moderate",
                confidence=0.65,
                sec_concern_domains=[],
            ),
            CompetitorEntry(
                display_name="Peer C",
                why_in_top_set="Adjacent platform competitor.",
                evidence_grade="weak",
                confidence=0.5,
                sec_concern_domains=[],
            ),
        ],
    )

    async def _fake_run(**_kwargs: object) -> tuple[CompetitorLandscapeLlm | None, list[str]]:
        return structured, []

    async def _fake_seed(**_kwargs: object) -> str:
        return "### Tavily seed (step 0 — test stub)\n(synthetic)"

    monkeypatch.setattr(
        "battlescope_api.graph.nodes.competitor_discover.fetch_tavily_top10_seed_block",
        _fake_seed,
    )
    monkeypatch.setattr(
        "battlescope_api.graph.nodes.competitor_discover.run_competitor_react_research",
        _fake_run,
    )

    state: GraphState = {
        "run_id": "r1",
        "thread_id": "t1",
        "company_name": "TargetCo",
        "company_profile": {
            "name": "TargetCo",
            "summary": "Enterprise widgets.",
            "earnings_call": {"symbol": "TGT", "quarter": "2025Q4", "strengths": [], "weaknesses": []},
        },
        "sec_risk_dossier": {
            "status": "ok",
            "risk_theme_bullets": ["Competition may erode margins.", "Supply chain concentration."],
        },
        "planner_notes": [],
        "trace_events": [],
    }
    out = await competitor_discover_node(state)
    ls = out.get("competitor_landscape") or {}
    assert ls.get("status") == "ok"
    assert ls.get("degraded") is False
    assert len(ls.get("competitors") or []) == 3
    events = out.get("trace_events") or []
    assert any(e.get("message") == "CompetitorDiscover" for e in events)
