from __future__ import annotations

import logging
import re
from typing import Any
from urllib.parse import urlencode

from langsmith import traceable

from battlescope_api.tools.tool_client import ToolClient

logger = logging.getLogger(__name__)

ALPHAVANTAGE_QUERY_URL = "https://www.alphavantage.co/query"
_QUARTER_RE = re.compile(r"^\d{4}Q[1-4]$", re.IGNORECASE)
_SYMBOL_RE = re.compile(r"^[A-Z0-9.\-]{1,20}$")


def _alphavantage_trace_inputs(inputs: dict) -> dict:
    return {
        "symbol": inputs.get("symbol"),
        "quarter": inputs.get("quarter"),
        "api_key_configured": bool(inputs.get("api_key")),
    }


@traceable(
    name="alphavantage_earnings_transcript",
    run_type="tool",
    process_inputs=_alphavantage_trace_inputs,
)
async def _earnings_call_transcript_traced(
    tool: ToolClient,
    api_key: str,
    symbol: str,
    quarter: str,
) -> dict[str, Any]:
    params = {
        "function": "EARNINGS_CALL_TRANSCRIPT",
        "symbol": symbol,
        "quarter": quarter,
        "apikey": api_key,
    }
    url = f"{ALPHAVANTAGE_QUERY_URL}?{urlencode(params)}"
    response = await tool.request("GET", url)
    if response.status_code >= 400:
        logger.warning(
            "alphavantage_http_error",
            extra={"status_code": response.status_code, "body": response.text[:300]},
        )
        return {
            "symbol": symbol,
            "quarter": quarter,
            "transcript": [],
            "error": f"HTTP {response.status_code}",
        }
    try:
        data: Any = response.json()
    except Exception as exc:
        logger.warning("alphavantage_json_error", extra={"error": str(exc)})
        return {"symbol": symbol, "quarter": quarter, "transcript": [], "error": "invalid JSON response"}

    if not isinstance(data, dict):
        return {"symbol": symbol, "quarter": quarter, "transcript": [], "error": "unexpected response shape"}

    if data.get("Error Message"):
        return {
            "symbol": data.get("symbol", symbol),
            "quarter": data.get("quarter", quarter),
            "transcript": [],
            "error": str(data["Error Message"]),
        }

    if "transcript" not in data and data.get("Information"):
        return {
            "symbol": symbol,
            "quarter": quarter,
            "transcript": [],
            "error": str(data["Information"]),
        }

    if "Note" in data and "transcript" not in data:
        return {"symbol": symbol, "quarter": quarter, "transcript": [], "error": str(data.get("Note", ""))}

    return data


def normalize_equity_symbol(raw: str) -> str | None:
    """Uppercase equity ticker; allow letters, digits, dot, hyphen (e.g. BRK.A)."""
    s = (raw or "").strip().upper()
    if not s or not _SYMBOL_RE.match(s):
        return None
    return s


def normalize_fiscal_quarter(raw: str) -> str | None:
    """Expect ``YYYYQn`` with n in 1..4 (e.g. ``2024Q1``)."""
    s = (raw or "").strip().upper()
    if not s or not _QUARTER_RE.match(s):
        return None
    return s


def format_earnings_transcript_for_llm(data: dict[str, Any], *, max_chars: int) -> str:
    """Turn API JSON into a single model-readable string (bounded length)."""
    err = data.get("error")
    if err:
        return f"(Alpha Vantage earnings transcript: {err})"

    symbol = data.get("symbol", "")
    quarter = data.get("quarter", "")
    rows = data.get("transcript")
    if not isinstance(rows, list) or not rows:
        return f"(Alpha Vantage: no transcript segments for {symbol!r} {quarter!r}.)"

    header = f"## Earnings call transcript\nsymbol={symbol} quarter={quarter}\n"
    lines: list[str] = [header]
    used = len(header)
    per_segment_cap = max(400, min(2500, max_chars // max(len(rows), 1)))

    for i, row in enumerate(rows, start=1):
        if not isinstance(row, dict):
            continue
        speaker = str(row.get("speaker") or "")
        title = str(row.get("title") or "")
        sentiment = str(row.get("sentiment") or "")
        content = str(row.get("content") or "").strip()
        if len(content) > per_segment_cap:
            content = content[:per_segment_cap] + "\n…[segment truncated]…"
        block = (
            f"### Segment {i}: {speaker} — {title}\n"
            f"sentiment={sentiment}\n{content}\n"
        )
        if used + len(block) > max_chars:
            lines.append(f"\n… ({len(rows) - i + 1} further segments omitted for length)\n")
            break
        lines.append(block)
        used += len(block)

    return "\n".join(lines).strip()


class AlphaVantageClient:
    """
    Alpha Vantage HTTP API (GET). Reusable by IntakeProfiler and future graph nodes.

    Docs: https://www.alphavantage.co/documentation/ — ``EARNINGS_CALL_TRANSCRIPT``.
    """

    def __init__(self, api_key: str | None, tool: ToolClient) -> None:
        self.api_key = api_key
        self._tool = tool

    async def earnings_call_transcript(self, symbol: str, quarter: str) -> dict[str, Any]:
        sym = normalize_equity_symbol(symbol)
        q = normalize_fiscal_quarter(quarter)
        if not sym:
            return {"symbol": symbol, "quarter": quarter, "transcript": [], "error": "invalid or empty symbol"}
        if not q:
            return {
                "symbol": sym,
                "quarter": quarter,
                "transcript": [],
                "error": "invalid quarter; use YYYYQ1..YYYYQ4 (e.g. 2024Q1)",
            }
        if not self.api_key:
            logger.info("alphavantage_skipped", extra={"reason": "missing_api_key"})
            return {"symbol": sym, "quarter": q, "transcript": [], "error": "ALPHA_VANTAGE_API_KEY not configured"}

        return await _earnings_call_transcript_traced(self._tool, self.api_key, sym, q)
