import uuid
from functools import lru_cache

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from battlescope_api.graph.builder import build_graph
from battlescope_api.graph.state import GraphState

router = APIRouter()


@lru_cache(maxsize=1)
def _compiled_graph():
    """Single compiled graph instance (safe while graph definition is static)."""
    return build_graph()


class RunCreateRequest(BaseModel):
    company_name: str | None = Field(default=None, description="Target company name")
    company_url: str | None = Field(default=None, description="Target company URL")


class RunSyncResponse(BaseModel):
    """
    Synchronous-style HTTP response after one graph execution (blocking until current nodes finish).
    Extend with more fields as you add nodes.
    """

    run_id: str
    thread_id: str
    stage: str
    company_profile: dict
    company_url_normalized: str | None = None
    planner_notes: list[str] = Field(default_factory=list)
    trace_events: list[dict] = Field(default_factory=list)
    sec_risk_dossier: dict = Field(
        default_factory=dict,
        description="10-K Item 1A distilled risk themes (after SecRisk10K node).",
    )


@router.post("", response_model=RunSyncResponse)
async def create_run(body: RunCreateRequest) -> RunSyncResponse:
    """
    Run the LangGraph through its current nodes (today: IntakeProfiler only) and return state.

    Use this for incremental HTTP testing; add SSE or background jobs later for long runs.
    """
    run_id = str(uuid.uuid4())
    thread_id = run_id

    initial: GraphState = {
        "run_id": run_id,
        "thread_id": thread_id,
        "loop_count": 0,
        "company_name": (body.company_name or "").strip(),
        "company_url": (body.company_url or "").strip(),
        "planner_notes": [],
        "trace_events": [],
    }

    try:
        final: GraphState = await _compiled_graph().ainvoke(initial)
    except Exception as exc:  # noqa: BLE001 — surface unexpected graph errors during development
        raise HTTPException(status_code=500, detail=f"graph_run_failed: {type(exc).__name__}: {exc}") from exc

    profile = final.get("company_profile") or {}
    return RunSyncResponse(
        run_id=run_id,
        thread_id=thread_id,
        stage=str(final.get("stage", "")),
        company_profile=profile,
        company_url_normalized=final.get("company_url_normalized"),
        planner_notes=list(final.get("planner_notes") or []),
        trace_events=list(final.get("trace_events") or []),
        sec_risk_dossier=dict(final.get("sec_risk_dossier") or {}),
    )
