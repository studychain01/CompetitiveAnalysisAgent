import json
import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from functools import lru_cache

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from battlescope_api.graph.builder import build_graph
from battlescope_api.graph.state import GraphState
from battlescope_api.services.run_initial_state import build_initial_graph_state
from battlescope_api.services.run_registry import consume, register

router = APIRouter()


@lru_cache(maxsize=1)
def _compiled_graph():
    """Single compiled graph instance (safe while graph definition is static)."""
    return build_graph()


class RunCreateRequest(BaseModel):
    company_name: str | None = Field(default=None, description="Target company name")
    company_url: str | None = Field(default=None, description="Target company URL")


class RunStreamStartResponse(BaseModel):
    run_id: str
    thread_id: str
    events_url: str


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
    competitor_landscape: dict = Field(
        default_factory=dict,
        description="3–6 competitors with SEC-theme mapping (after CompetitorDiscover node).",
    )
    peer_research_digests: dict = Field(
        default_factory=dict,
        description="Up to 3 parallel deep peer digests (after PeerResearchParallel node).",
    )
    competitive_strategy: dict = Field(
        default_factory=dict,
        description="Prioritized competitive strategy (after CompetitiveStrategy node).",
    )


def _graph_state_to_stream_payload(state: GraphState) -> dict:
    """Subset aligned with ``RunSyncResponse`` for client merge (excluding run_id/thread_id)."""
    profile = state.get("company_profile") or {}
    return {
        "stage": str(state.get("stage", "")),
        "company_profile": dict(profile) if isinstance(profile, dict) else {},
        "company_url_normalized": state.get("company_url_normalized"),
        "planner_notes": list(state.get("planner_notes") or []),
        "trace_events": list(state.get("trace_events") or []),
        "sec_risk_dossier": dict(state.get("sec_risk_dossier") or {}),
        "competitor_landscape": dict(state.get("competitor_landscape") or {}),
        "peer_research_digests": dict(state.get("peer_research_digests") or {}),
        "competitive_strategy": dict(state.get("competitive_strategy") or {}),
    }


def _sse_data_line(obj: dict) -> str:
    return f"data: {json.dumps(obj, default=str)}\n\n"


async def _run_event_generator(run_id: str) -> AsyncIterator[str]:
    def _ts() -> str:
        return datetime.now(UTC).isoformat().replace("+00:00", "Z")
    initial = consume(run_id)
    if initial is None:
        yield _sse_data_line(
            {
                "v": 1,
                "type": "error",
                "run_id": run_id,
                "ts": _ts(),
                "payload": {"detail": "unknown_or_expired_run_id"},
            }
        )
        return

    graph = _compiled_graph()
    last: GraphState | None = None
    try:
        async for _mode, snapshot in graph.astream(initial, stream_mode=["values"]):
            if not isinstance(snapshot, dict):
                continue
            last = snapshot  # type: ignore[assignment]
            yield _sse_data_line(
                {
                    "v": 1,
                    "type": "state",
                    "run_id": run_id,
                    "ts": _ts(),
                    "payload": _graph_state_to_stream_payload(last),
                }
            )
    except Exception as exc:  # noqa: BLE001
        yield _sse_data_line(
            {
                "v": 1,
                "type": "error",
                "run_id": run_id,
                "ts": _ts(),
                "payload": {"detail": f"{type(exc).__name__}: {exc}"},
            }
        )
        return

    if last is not None:
        yield _sse_data_line(
            {
                "v": 1,
                "type": "complete",
                "run_id": run_id,
                "ts": _ts(),
                "payload": _graph_state_to_stream_payload(last),
            }
        )


@router.post("/start", response_model=RunStreamStartResponse, status_code=202)
async def start_stream_run(body: RunCreateRequest) -> RunStreamStartResponse:
    """
    Register initial graph state for a later ``GET /runs/{run_id}/events`` SSE stream.
    Does not execute the graph (see streaming endpoint).
    """
    run_id = str(uuid.uuid4())
    thread_id = run_id
    initial = build_initial_graph_state(
        run_id=run_id,
        thread_id=thread_id,
        company_name=(body.company_name or "").strip(),
        company_url=(body.company_url or "").strip(),
    )
    register(run_id, initial)
    events_url = f"/runs/{run_id}/events"
    return RunStreamStartResponse(
        run_id=run_id,
        thread_id=thread_id,
        events_url=events_url,
    )


@router.get("/{run_id}/events")
async def stream_run_events(run_id: str) -> StreamingResponse:
    """Server-Sent Events: stream graph state snapshots until ``complete`` or ``error``."""
    return StreamingResponse(
        _run_event_generator(run_id),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("", response_model=RunSyncResponse)
async def create_run(body: RunCreateRequest) -> RunSyncResponse:
    """
    Run the LangGraph through its current nodes (today: IntakeProfiler only) and return state.

    Use this for incremental HTTP testing; use ``POST /runs/start`` + ``GET /runs/{id}/events`` for SSE.
    """
    run_id = str(uuid.uuid4())
    thread_id = run_id

    initial = build_initial_graph_state(
        run_id=run_id,
        thread_id=thread_id,
        company_name=(body.company_name or "").strip(),
        company_url=(body.company_url or "").strip(),
    )

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
        competitor_landscape=dict(final.get("competitor_landscape") or {}),
        peer_research_digests=dict(final.get("peer_research_digests") or {}),
        competitive_strategy=dict(final.get("competitive_strategy") or {}),
    )
