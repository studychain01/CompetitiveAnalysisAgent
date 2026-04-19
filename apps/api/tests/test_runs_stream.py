"""SSE: POST /runs/start + GET /runs/{run_id}/events."""

from __future__ import annotations

import json
from typing import Any

import pytest
from fastapi.testclient import TestClient

from battlescope_api.api.routes import runs as runs_module
from battlescope_api.main import app
from battlescope_api.services import run_registry


class _StubCompiledGraph:
    """Minimal graph stand-in: two ``values`` snapshots then done."""

    async def astream(self, initial: dict[str, Any], stream_mode: list[str] | None = None):
        s1 = {**initial, "stage": "intake", "company_profile": {"name": "StubCo"}}
        s2 = {
            **initial,
            "stage": "competitive_strategy",
            "company_profile": {"name": "StubCo"},
            "sec_risk_dossier": {"status": "skipped"},
            "competitor_landscape": {},
            "peer_research_digests": {},
            "competitive_strategy": {"status": "ok"},
            "planner_notes": ["done"],
            "trace_events": [{"event_type": "node_end", "run_id": initial["run_id"], "message": "x", "payload": {}}],
        }
        yield ("values", s1)
        yield ("values", s2)

    async def ainvoke(self, initial: dict[str, Any]) -> dict[str, Any]:
        out = {**initial}
        out.update(
            {
                "stage": "competitive_strategy",
                "company_profile": {"name": "StubCo"},
                "sec_risk_dossier": {"status": "skipped"},
                "competitor_landscape": {},
                "peer_research_digests": {},
                "competitive_strategy": {"status": "ok"},
                "planner_notes": [],
                "trace_events": [],
            }
        )
        return out


def _parse_sse_data_lines(raw: bytes) -> list[dict[str, Any]]:
    text = raw.decode("utf-8")
    events: list[dict[str, Any]] = []
    for block in text.split("\n\n"):
        block = block.strip()
        if not block.startswith("data:"):
            continue
        line = block[5:].strip()
        events.append(json.loads(line))
    return events


@pytest.fixture(autouse=True)
def _clear_registry():
    run_registry.clear_for_tests()
    yield
    run_registry.clear_for_tests()


def test_stream_start_then_sse_events(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(runs_module, "build_graph", lambda: _StubCompiledGraph())
    runs_module._compiled_graph.cache_clear()

    client = TestClient(app)
    start = client.post("/runs/start", json={"company_name": "Acme", "company_url": "https://acme.test"})
    assert start.status_code == 202
    meta = start.json()
    run_id = meta["run_id"]
    assert meta["thread_id"] == run_id
    assert meta["events_url"] == f"/runs/{run_id}/events"

    with client.stream("GET", f"/runs/{run_id}/events") as stream:
        assert stream.status_code == 200
        assert "text/event-stream" in (stream.headers.get("content-type") or "")
        body = stream.read()

    events = _parse_sse_data_lines(body)
    types = [e.get("type") for e in events]
    assert "state" in types
    assert types[-1] == "complete"
    assert events[-1]["run_id"] == run_id
    assert events[-1]["payload"]["stage"] == "competitive_strategy"


def test_stream_start_rejects_both_identifiers_empty() -> None:
    runs_module._compiled_graph.cache_clear()
    client = TestClient(app)
    for payload in ({}, {"company_name": "", "company_url": ""}, {"company_name": "  ", "company_url": "\t"}):
        r = client.post("/runs/start", json=payload)
        assert r.status_code == 422


def test_stream_start_accepts_url_only(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(runs_module, "build_graph", lambda: _StubCompiledGraph())
    runs_module._compiled_graph.cache_clear()
    client = TestClient(app)
    start = client.post("/runs/start", json={"company_url": "https://acme.test"})
    assert start.status_code == 202


def test_stream_unknown_run_id_yields_error_event() -> None:
    runs_module._compiled_graph.cache_clear()
    client = TestClient(app)
    with client.stream("GET", "/runs/00000000-0000-0000-0000-000000000000/events") as stream:
        assert stream.status_code == 200
        body = stream.read()
    events = _parse_sse_data_lines(body)
    assert len(events) == 1
    assert events[0]["type"] == "error"
    assert "unknown_or_expired" in str(events[0]["payload"].get("detail", ""))
