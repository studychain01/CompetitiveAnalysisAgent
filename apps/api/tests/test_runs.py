import pytest
from fastapi.testclient import TestClient

from battlescope_api.api.routes import runs as runs_module
from battlescope_api.main import app
from battlescope_api.models.competitor_landscape import CompetitorEntry, CompetitorLandscapeLlm


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
    runs_module._compiled_graph.cache_clear()

    client = TestClient(app)
    response = client.post("/runs", json={"company_name": "ExampleCo"})
    assert response.status_code == 200
    body = response.json()
    assert body["run_id"]
    assert body["thread_id"] == body["run_id"]
    assert body["stage"] == "competitor_discover"
    assert "sec_risk_dossier" in body
    assert "competitor_landscape" in body
    # Name may be canonicalized when external keys are present (Tavily/ReAct); keep a loose check.
    assert body["company_profile"].get("name")
    assert "example" in body["company_profile"]["name"].lower()
    assert isinstance(body["planner_notes"], list)
    assert isinstance(body["trace_events"], list)
