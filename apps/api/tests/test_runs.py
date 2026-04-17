from fastapi.testclient import TestClient

from battlescope_api.main import app


def test_create_run_invokes_graph_and_returns_intake_state() -> None:
    client = TestClient(app)
    response = client.post("/runs", json={"company_name": "ExampleCo"})
    assert response.status_code == 200
    body = response.json()
    assert body["run_id"]
    assert body["thread_id"] == body["run_id"]
    assert body["stage"] == "sec_risk"
    assert "sec_risk_dossier" in body
    # Name may be canonicalized when external keys are present (Tavily/ReAct); keep a loose check.
    assert body["company_profile"].get("name")
    assert "example" in body["company_profile"]["name"].lower()
    assert isinstance(body["planner_notes"], list)
    assert isinstance(body["trace_events"], list)
