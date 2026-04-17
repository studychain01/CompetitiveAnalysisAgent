from typing import Any, TypedDict


class GraphState(TypedDict, total=False):
    """
    Agent state. Lists like ``trace_events`` / ``planner_notes`` are replaced with merged
    full lists per node return (nodes read prior state, append, return new list).
    """

    run_id: str
    thread_id: str
    loop_count: int

    company_name: str
    company_url: str

    company_url_normalized: str | None
    company_profile: dict[str, Any]
    planner_notes: list[str]

    trace_events: list[dict[str, Any]]
    stage: str
    
    # Latest 10-K Item 1A risk themes (see ``sec_risk_node``); optional until that node runs.
    sec_risk_dossier: dict[str, Any]

    # Competitor shortlist + SEC-theme mapping (see ``competitor_discover_node``).
    competitor_landscape: dict[str, Any]
