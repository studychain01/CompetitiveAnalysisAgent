from typing import Any, Literal

from pydantic import BaseModel, Field

TraceEventType = Literal[
    "node_start",
    "node_end",
    "tool_start",
    "tool_end",
    "degraded",
    "retry",
    "branch_decision",
    "final",
]


class TraceEvent(BaseModel):
    event_type: TraceEventType
    run_id: str
    message: str
    payload: dict[str, Any] = Field(default_factory=dict)
