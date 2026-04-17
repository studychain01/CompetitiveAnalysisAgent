from __future__ import annotations

import httpx
import pytest

from battlescope_api.tools.alphavantage_client import (
    AlphaVantageClient,
    format_earnings_transcript_for_llm,
    normalize_equity_symbol,
    normalize_fiscal_quarter,
)
from battlescope_api.tools.tool_client import ToolClient


def test_normalize_equity_symbol() -> None:
    assert normalize_equity_symbol(" ibm ") == "IBM"
    assert normalize_equity_symbol("BRK.A") == "BRK.A"
    assert normalize_equity_symbol("") is None
    assert normalize_equity_symbol("BAD@SYM") is None


def test_normalize_fiscal_quarter() -> None:
    assert normalize_fiscal_quarter("2024q1") == "2024Q1"
    assert normalize_fiscal_quarter("2024Q4") == "2024Q4"
    assert normalize_fiscal_quarter("2024Q5") is None
    assert normalize_fiscal_quarter("") is None


def test_format_earnings_transcript_for_llm_error() -> None:
    text = format_earnings_transcript_for_llm({"error": "rate limit"}, max_chars=500)
    assert "rate limit" in text


def test_format_earnings_transcript_for_llm_segments() -> None:
    data = {
        "symbol": "IBM",
        "quarter": "2024Q1",
        "transcript": [
            {
                "speaker": "A",
                "title": "CEO",
                "content": "We grew software.",
                "sentiment": "0.7",
            }
        ],
    }
    text = format_earnings_transcript_for_llm(data, max_chars=2000)
    assert "IBM" in text
    assert "2024Q1" in text
    assert "software" in text


@pytest.mark.asyncio
async def test_alpha_vantage_earnings_call_transcript_http() -> None:
    body = {
        "symbol": "IBM",
        "quarter": "2024Q1",
        "transcript": [
            {
                "speaker": "CEO",
                "title": "CEO",
                "content": "Opening remarks.",
                "sentiment": "0.6",
            }
        ],
    }

    def handler(request: httpx.Request) -> httpx.Response:
        u = str(request.url)
        assert "alphavantage.co" in u
        assert "EARNINGS_CALL_TRANSCRIPT" in u
        assert "symbol=IBM" in u
        assert "quarter=2024Q1" in u
        return httpx.Response(200, json=body)

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport, timeout=httpx.Timeout(5.0)) as raw:
        tc = ToolClient(raw, retryable_methods=frozenset({"GET", "POST"}))
        av = AlphaVantageClient("test-key", tc)
        out = await av.earnings_call_transcript("ibm", "2024q1")

    assert out.get("symbol") == "IBM"
    assert isinstance(out.get("transcript"), list)
    assert len(out["transcript"]) == 1


@pytest.mark.asyncio
async def test_alpha_vantage_missing_key() -> None:
    async with httpx.AsyncClient(timeout=httpx.Timeout(5.0)) as raw:
        tc = ToolClient(raw, retryable_methods=frozenset({"GET", "POST"}))
        av = AlphaVantageClient(None, tc)
        out = await av.earnings_call_transcript("IBM", "2024Q1")
    assert out.get("error")
    assert out.get("transcript") == []
