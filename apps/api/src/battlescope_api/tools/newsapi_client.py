from __future__ import annotations

import logging
from typing import Any
from urllib.parse import urlencode

from langsmith import traceable

from battlescope_api.tools.tool_client import ToolClient

logger = logging.getLogger(__name__)

NEWSAPI_EVERYTHING_URL = "https://newsapi.org/v2/everything"


def _newsapi_trace_inputs(inputs: dict) -> dict:
    return {
        "q": inputs.get("q"),
        "page_size": inputs.get("page_size"),
        "api_key_configured": bool(inputs.get("api_key")),
    }


@traceable(
    name="newsapi_everything",
    run_type="tool",
    process_inputs=_newsapi_trace_inputs,
)
async def _newsapi_everything_traced(
    tool: ToolClient,
    api_key: str,
    query: str,
    *,
    page_size: int,
) -> dict[str, Any]:
    params: dict[str, str | int] = {
        "q": query,
        "language": "en",
        "sortBy": "relevancy",
        "pageSize": page_size,
        "apiKey": api_key,
    }
    url = f"{NEWSAPI_EVERYTHING_URL}?{urlencode(params)}"
    response = await tool.request("GET", url, timeout=30.0)
    if response.status_code >= 400:
        logger.warning(
            "newsapi_http_error",
            extra={"status_code": response.status_code, "body": response.text[:500]},
        )
        return {"status": "error", "articles": [], "message": response.text[:300]}
    return response.json()


class NewsApiClient:
    """NewsAPI.org v2 `everything` search (GET)."""

    def __init__(self, api_key: str | None, tool: ToolClient) -> None:
        self.api_key = api_key
        self._tool = tool

    async def everything(self, query: str, *, page_size: int = 15) -> dict[str, Any]:
        if not self.api_key:
            logger.info("newsapi_skipped", extra={"reason": "missing_api_key"})
            return {"status": "ok", "totalResults": 0, "articles": [], "query": query}
        bounded = max(1, min(int(page_size), 30))
        return await _newsapi_everything_traced(
            self._tool,
            self.api_key,
            query,
            page_size=bounded,
        )


def format_newsapi_block(payload: dict[str, Any], *, max_chars: int = 12_000) -> str:
    """Turn NewsAPI JSON into a compact string for LLM tool results."""
    if payload.get("status") == "error" or payload.get("message"):
        return f"(NewsAPI error: {payload.get('message', 'unknown')})"
    articles = payload.get("articles") or []
    lines: list[str] = []
    for idx, art in enumerate(articles, start=1):
        title = art.get("title") or ""
        url = art.get("url") or ""
        desc = (art.get("description") or art.get("content") or "").strip()
        lines.append(f"{idx}. {title}\n   URL: {url}\n   Snippet: {desc[:600]}")
    text = "\n\n".join(lines) if lines else "(no NewsAPI articles)"
    if len(text) > max_chars:
        return text[: max_chars - 24] + "\n...[truncated]..."
    return text
