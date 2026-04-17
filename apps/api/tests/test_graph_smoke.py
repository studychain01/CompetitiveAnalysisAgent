import pytest

from battlescope_api.graph.builder import build_graph


@pytest.mark.asyncio
async def test_graph_intake_smoke() -> None:
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
    assert result.get("stage") == "sec_risk"
    assert isinstance(result.get("sec_risk_dossier"), dict)
    assert result.get("company_profile", {}).get("name") == "ExampleCo"
    assert result.get("trace_events")
