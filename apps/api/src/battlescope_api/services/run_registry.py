"""
In-memory store for stream-run initial state (``POST /runs/start`` → ``GET /runs/{id}/events``).

Single-process / single-worker only; entries are removed on consume. For horizontal scale, use Redis
or a job queue instead.
"""

from __future__ import annotations

import threading

from battlescope_api.graph.state import GraphState

_lock = threading.Lock()
_runs: dict[str, GraphState] = {}


def register(run_id: str, initial: GraphState) -> None:
    with _lock:
        _runs[run_id] = initial


def consume(run_id: str) -> GraphState | None:
    """Remove and return initial state for ``run_id``, or ``None`` if missing / already consumed."""
    with _lock:
        return _runs.pop(run_id, None)


def clear_for_tests() -> None:
    with _lock:
        _runs.clear()
