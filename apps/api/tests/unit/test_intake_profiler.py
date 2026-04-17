from __future__ import annotations

import httpx
import pytest

from battlescope_api.graph.nodes.intake import normalize_company_url, run_intake_profiler
from battlescope_api.graph.state import GraphState
from battlescope_api.models.company_profile import CompanyProfileLlm
from battlescope_api.settings import get_settings

# Long enough fake key so settings heuristics treat it as a plausible OpenAI platform secret.
_FAKE_OPENAI_KEY = "sk-proj-0123456789abcdefghijklmnopqrstuvwxyzABCDEFGH"


@pytest.fixture
def clear_settings_cache():
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.mark.asyncio
async def test_intake_name_only_no_keys_heuristic(
    monkeypatch: pytest.MonkeyPatch, clear_settings_cache
) -> None:
    # Shadow values from ``apps/api/.env`` (pydantic still reads the file unless env wins).
    monkeypatch.setenv("TAVILY_API_KEY", "")
    monkeypatch.setenv("OPENAI_API_KEY", "")
    monkeypatch.setenv("FIRECRAWL_API_KEY", "")
    get_settings.cache_clear()

    state: GraphState = {
        "run_id": "r1",
        "thread_id": "t1",
        "company_name": "ExampleCo",
        "planner_notes": [],
        "trace_events": [],
    }
    out = await run_intake_profiler(state)
    profile = out["company_profile"]
    assert profile["name"] == "ExampleCo"
    assert profile.get("intake_degraded") is True
    assert "OPENAI_API_KEY missing" in " ".join(out.get("planner_notes", []))


@pytest.mark.asyncio
async def test_intake_bad_url_normalized_none(
    monkeypatch: pytest.MonkeyPatch, clear_settings_cache
) -> None:
    monkeypatch.setenv("TAVILY_API_KEY", "")
    monkeypatch.setenv("OPENAI_API_KEY", "")
    monkeypatch.setenv("FIRECRAWL_API_KEY", "")
    get_settings.cache_clear()

    state: GraphState = {
        "run_id": "r1",
        "thread_id": "t1",
        "company_name": "BrokenCo",
        "company_url": "not-a-valid-url!!!",
        "planner_notes": [],
        "trace_events": [],
    }
    out = await run_intake_profiler(state)
    assert out.get("company_url_normalized") is None
    assert out["company_profile"]["name"] == "BrokenCo"
    assert "could not be normalized" in " ".join(out.get("planner_notes", []))


@pytest.mark.asyncio
async def test_intake_react_path_mocked_structured_profile(
    monkeypatch: pytest.MonkeyPatch, clear_settings_cache
) -> None:
    """ReAct path returns ``CompanyProfileLlm`` from the subgraph; mock it to avoid real OpenAI."""
    monkeypatch.setenv("TAVILY_API_KEY", "tvly-test")
    monkeypatch.setenv("OPENAI_API_KEY", _FAKE_OPENAI_KEY)
    monkeypatch.setenv("FIRECRAWL_API_KEY", "fc-test")
    get_settings.cache_clear()

    structured = CompanyProfileLlm(
        name="Acme Robotics",
        category="warehouse automation",
        buyer="ops leaders",
        business_model="subscription",
        summary="Acme sells AMRs to mid-market warehouses.",
        uncertainties=[],
        primary_domain="acmerobotics.example",
        category_alternatives=[],
        profile_confidence=0.9,
        earnings_call={
            "symbol": None,
            "quarter": None,
            "strengths": ["Warehouse automation focus", "Subscription revenue"],
            "weaknesses": ["Execution risk in new verticals"],
        },
    )

    async def _fake_run_intake_react_research(**_kwargs: object) -> tuple[CompanyProfileLlm | None, list[str]]:
        return structured, []

    monkeypatch.setattr(
        "battlescope_api.graph.nodes.intake.run_intake_react_research",
        _fake_run_intake_react_research,
    )

    state: GraphState = {
        "run_id": "r1",
        "thread_id": "t1",
        "company_name": "Acme Robotics",
        "company_url": "https://acmerobotics.example",
        "planner_notes": [],
        "trace_events": [],
    }
    out = await run_intake_profiler(state)
    profile = out["company_profile"]
    assert profile["name"] == "Acme Robotics"
    assert profile["category"] == "warehouse automation"
    ec = profile["earnings_call"]
    assert ec["strengths"]
    assert ec["weaknesses"]
    assert out.get("company_url_normalized", "").startswith("https://")


@pytest.mark.asyncio
async def test_intake_react_failure_falls_back_to_heuristic_with_mocks(
    monkeypatch: pytest.MonkeyPatch, clear_settings_cache
) -> None:
    monkeypatch.setenv("TAVILY_API_KEY", "tvly-test")
    monkeypatch.setenv("OPENAI_API_KEY", _FAKE_OPENAI_KEY)
    monkeypatch.setenv("FIRECRAWL_API_KEY", "fc-test")
    get_settings.cache_clear()

    async def _fake_run_fail(**_kwargs: object) -> tuple[CompanyProfileLlm | None, list[str]]:
        return None, ["Intake ReAct failed (RuntimeError): forced"]

    monkeypatch.setattr(
        "battlescope_api.graph.nodes.intake.run_intake_react_research",
        _fake_run_fail,
    )

    def handler(request: httpx.Request) -> httpx.Response:
        host = request.url.host or ""
        if host == "api.tavily.com":
            return httpx.Response(
                200,
                json={
                    "results": [
                        {
                            "title": "Acme Robotics overview",
                            "url": "https://acmerobotics.example/about",
                            "content": "Acme makes warehouse robots.",
                        }
                    ]
                },
            )
        if host == "api.firecrawl.dev":
            return httpx.Response(
                200,
                json={"success": True, "data": {"markdown": "# Acme\nRobotics vendor."}},
            )
        return httpx.Response(404, json={"error": "unexpected host", "host": host})

    transport = httpx.MockTransport(handler)

    def _client_factory() -> httpx.AsyncClient:
        return httpx.AsyncClient(transport=transport, timeout=httpx.Timeout(5.0))

    monkeypatch.setattr("battlescope_api.graph.nodes.intake.create_http_client", _client_factory)

    state: GraphState = {
        "run_id": "r1",
        "thread_id": "t1",
        "company_name": "Acme Robotics",
        "company_url": "https://acmerobotics.example",
        "planner_notes": [],
        "trace_events": [],
    }
    out = await run_intake_profiler(state)
    assert "forced" in " ".join(out.get("planner_notes", []))
    profile = out["company_profile"]
    assert profile["name"] == "Acme Robotics"
    assert profile.get("intake_degraded") is True
    assert "warehouse robots" in profile.get("summary", "").lower() or "Acme" in profile.get("summary", "")


def test_normalize_company_url_adds_scheme() -> None:
    url, domain = normalize_company_url("example.com/about")
    assert url == "https://example.com/about"
    assert domain == "example.com"
