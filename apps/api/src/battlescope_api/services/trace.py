from typing import Any


def append_trace_event(
    events: list[dict[str, Any]],
    event_type: str,
    run_id: str,
    message: str,
    payload: dict[str, Any] | None = None,
) -> None:
    events.append(
        {
            "event_type": event_type,
            "run_id": run_id,
            "message": message,
            "payload": payload or {},
        }
    )
