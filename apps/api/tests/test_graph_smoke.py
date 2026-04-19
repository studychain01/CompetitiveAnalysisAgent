import pytest

from battlescope_api.graph.builder import build_graph
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


@pytest.mark.asyncio
async def test_graph_intake_smoke(monkeypatch: pytest.MonkeyPatch) -> None:
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

    async def _stub_tavily_seed(**_kwargs: object) -> str:
        return ""

    monkeypatch.setattr(
        "battlescope_api.graph.nodes.competitor_discover.fetch_tavily_top10_seed_block",
        _stub_tavily_seed,
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
                    AheadAxis(
                        axis="brand",
                        rationale="stub",
                        source_urls=[],
                        confidence=0.4,
                    )
                ],
                power_user_hypothesis=PowerUserHypothesis(
                    segment_label="stub",
                    jobs_to_be_done=[],
                    signals=[],
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
            executive_summary="stub exec",
            prioritized_moves=[
                PrioritizedMove(
                    rank=1,
                    title="stub",
                    rationale="r",
                    horizon="short",
                    effort="low_hanging",
                    owner_hint="product",
                )
            ],
            short_term_plan=HorizonPlan(horizon_label="0–90d", bullets=["x"]),
            long_term_plan=HorizonPlan(horizon_label="6–24m", bullets=["y"]),
        )

    monkeypatch.setattr(
        "battlescope_api.graph.nodes.competitive_strategy._synthesize_final_strategy",
        _stub_strategy,
    )

    graph = build_graph()
    result = await graph.ainvoke(
        {
            "run_id": "test-run",
            "thread_id": "test-thread",
            "company_name": "ExampleCo",
            "planner_notes": [],
            "trace_events": [],
        }
    )
    assert result.get("stage") == "competitive_strategy"
    assert isinstance(result.get("sec_risk_dossier"), dict)
    assert isinstance(result.get("competitor_landscape"), dict)
    assert isinstance(result.get("peer_research_digests"), dict)
    assert isinstance(result.get("competitive_strategy"), dict)
    name = (result.get("company_profile") or {}).get("name") or ""
    assert "example" in name.lower()
    assert result.get("trace_events")
