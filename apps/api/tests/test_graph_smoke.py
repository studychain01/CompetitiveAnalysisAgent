import pytest

from battlescope_api.graph.builder import build_graph
from battlescope_api.models.competitor_landscape import CompetitorEntry, CompetitorLandscapeLlm


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

    monkeypatch.setattr(
        "battlescope_api.graph.nodes.competitor_discover.run_competitor_react_research",
        _stub_competitor_react,
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
    assert result.get("stage") == "competitor_discover"
    assert isinstance(result.get("sec_risk_dossier"), dict)
    assert isinstance(result.get("competitor_landscape"), dict)
    name = (result.get("company_profile") or {}).get("name") or ""
    assert "example" in name.lower()
    assert result.get("trace_events")
