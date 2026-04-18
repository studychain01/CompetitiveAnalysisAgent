"""Build LangGraph ``GraphState`` for a new run (shared by sync ``POST /runs`` and stream ``POST /runs/start``)."""

from __future__ import annotations

from battlescope_api.graph.state import GraphState


def build_initial_graph_state(
    *,
    run_id: str,
    thread_id: str,
    company_name: str,
    company_url: str,
) -> GraphState:
    return {
        "run_id": run_id,
        "thread_id": thread_id,
        "loop_count": 0,
        "company_name": company_name,
        "company_url": company_url,
        "planner_notes": [],
        "trace_events": [],
    }
