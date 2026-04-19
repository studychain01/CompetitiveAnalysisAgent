from __future__ import annotations

import pytest

from battlescope_api.graph.nodes.sec_risk import sec_risk_node
from battlescope_api.graph.state import GraphState
from battlescope_api.settings import get_settings


@pytest.fixture
def clear_settings_cache():
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.mark.asyncio
async def test_sec_risk_skipped_without_fmp_key(
    monkeypatch: pytest.MonkeyPatch, clear_settings_cache
) -> None:
    # Override any FMP key from ``.env`` (pydantic loads the file even when env var is unset).
    monkeypatch.setenv("FMP_API_KEY", "")
    monkeypatch.setenv("FINANCIAL_MODELING_PREP_API_KEY", "")
    # Disable web fallback so this test stays deterministic (no live Tavily/OpenAI).
    monkeypatch.setenv("OPENAI_API_KEY", "")
    monkeypatch.setenv("TAVILY_API_KEY", "")
    monkeypatch.setenv("FIRECRAWL_API_KEY", "")
    get_settings.cache_clear()

    state: GraphState = {
        "run_id": "r1",
        "thread_id": "t1",
        "company_profile": {"earnings_call": {"symbol": "AAPL"}},
        "planner_notes": [],
        "trace_events": [],
    }
    out = await sec_risk_node(state)
    dossier = out.get("sec_risk_dossier") or {}
    assert dossier.get("status") == "skipped"
    assert "FMP_API_KEY" in (dossier.get("reason") or "")


@pytest.mark.asyncio
async def test_sec_risk_skipped_without_ticker(
    monkeypatch: pytest.MonkeyPatch, clear_settings_cache
) -> None:
    monkeypatch.setenv("FMP_API_KEY", "dummy-fmp-key-for-test")
    monkeypatch.setenv("OPENAI_API_KEY", "")
    monkeypatch.setenv("TAVILY_API_KEY", "")
    monkeypatch.setenv("FIRECRAWL_API_KEY", "")
    get_settings.cache_clear()

    state: GraphState = {
        "run_id": "r1",
        "thread_id": "t1",
        "company_profile": {"earnings_call": {"symbol": None}},
        "planner_notes": [],
        "trace_events": [],
    }
    out = await sec_risk_node(state)
    dossier = out.get("sec_risk_dossier") or {}
    assert dossier.get("status") == "skipped"
    assert "ticker" in (dossier.get("reason") or "").lower()
