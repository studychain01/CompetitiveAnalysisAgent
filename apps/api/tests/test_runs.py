import pytest
from fastapi.testclient import TestClient

from battlescope_api.api.routes import runs as runs_module
from battlescope_api.main import app
from battlescope_api.models.competitor_landscape import CompetitorEntry, CompetitorLandscapeLlm
from battlescope_api.models.competitive_strategy import (
    CompetitiveStrategyLlm,
    HorizonPlan,
    PrioritizedMove,
)
from battlescope_api.models.peer_research_digest import (
    AheadAxis,
    PeerResearchDigestLlm,
    PowerUserHypothesis,
)


def test_create_run_invokes_graph_and_returns_intake_state(monkeypatch: pytest.MonkeyPatch) -> None:
    async def _stub_competitor_react(**_kwargs: object) -> tuple[CompetitorLandscapeLlm | None, list[str]]:
        return (
            CompetitorLandscapeLlm(
                target_company_context_note="stub",
                competitors=[
                    CompetitorEntry(
                        display_name="Stub Peer One",
                        why_in_top_set="stub",
                        evidence_grade="weak",
                        confidence=0.4,
                        sec_concern_domains=[],
                    ),
                    CompetitorEntry(
                        display_name="Stub Peer Two",
                        why_in_top_set="stub",
                        evidence_grade="weak",
                        confidence=0.4,
                        sec_concern_domains=[],
                    ),
                    CompetitorEntry(
                        display_name="Stub Peer Three",
                        why_in_top_set="stub",
                        evidence_grade="weak",
                        confidence=0.4,
                        sec_concern_domains=[],
                    ),
                ],
            ),
            [],
        )

    monkeypatch.setattr(
        "battlescope_api.graph.nodes.competitor_discover.run_competitor_react_research",
        _stub_competitor_react,
    )

    async def _stub_peer_react(**_kwargs: object) -> tuple[PeerResearchDigestLlm | None, list[str]]:
        return (
            PeerResearchDigestLlm(
                peer_display_name="stub",
                ahead_axes=[
                    AheadAxis(axis="pricing", rationale="stub", source_urls=[], confidence=0.4),
                ],
                power_user_hypothesis=PowerUserHypothesis(
                    segment_label="stub", jobs_to_be_done=[], signals=[]
                ),
                evidence_notes="stub",
                overall_confidence=0.4,
            ),
            [],
        )

    monkeypatch.setattr(
        "battlescope_api.graph.nodes.peer_research_parallel.run_peer_react_research",
        _stub_peer_react,
    )

    async def _stub_strategy(**_kwargs: object) -> CompetitiveStrategyLlm | None:
        return CompetitiveStrategyLlm(
            executive_summary="stub",
            prioritized_moves=[
                PrioritizedMove(
                    rank=1,
                    title="t",
                    rationale="r",
                    horizon="short",
                    effort="low_hanging",
                    owner_hint="product",
                )
            ],
            short_term_plan=HorizonPlan(horizon_label="0–90d", bullets=[]),
            long_term_plan=HorizonPlan(horizon_label="6–24m", bullets=[]),
        )

    monkeypatch.setattr(
        "battlescope_api.graph.nodes.competitive_strategy._synthesize_final_strategy",
        _stub_strategy,
    )
    runs_module._compiled_graph.cache_clear()

    client = TestClient(app)
    response = client.post("/runs", json={"company_name": "ExampleCo"})
    assert response.status_code == 200
    body = response.json()
    assert body["run_id"]
    assert body["thread_id"] == body["run_id"]
    assert body["stage"] == "competitive_strategy"
    assert "sec_risk_dossier" in body
    assert "competitor_landscape" in body
    assert "peer_research_digests" in body
    assert "competitive_strategy" in body
    # Name may be canonicalized when external keys are present (Tavily/ReAct); keep a loose check.
    assert body["company_profile"].get("name")
    assert "example" in body["company_profile"]["name"].lower()
    assert isinstance(body["planner_notes"], list)
    assert isinstance(body["trace_events"], list)


def test_create_run_rejects_both_identifiers_empty() -> None:
    runs_module._compiled_graph.cache_clear()
    client = TestClient(app)
    r = client.post("/runs", json={"company_name": "", "company_url": None})
    assert r.status_code == 422
