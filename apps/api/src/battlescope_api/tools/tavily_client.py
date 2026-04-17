from __future__ import annotations

import logging
from typing import Any

from langsmith import traceable

from battlescope_api.tools.tool_client import ToolClient

logger = logging.getLogger(__name__)

TAVILY_SEARCH_URL = "https://api.tavily.com/search"


def _tavily_trace_inputs(inputs: dict) -> dict:
    """Avoid logging Tavily API keys; keep query-level observability."""
    return {
        "query": inputs.get("query"),
        "max_results": inputs.get("max_results"),
        "api_key_configured": bool(inputs.get("api_key")),
    }


@traceable(
    name="tavily_search",
    run_type="tool",
    process_inputs=_tavily_trace_inputs,
)
async def _tavily_search_traced(
    tool: ToolClient,
    api_key: str,
    query: str,
    *,
    max_results: int,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "api_key": api_key,
        "query": query,
        "max_results": max_results,
        "search_depth": "basic",
        "include_answer": False,
    }
    response = await tool.request(
        "POST",
        TAVILY_SEARCH_URL,
        json=payload,
        headers={"Content-Type": "application/json"},
    )
    if response.status_code >= 400:
        logger.warning(
            "tavily_http_error",
            extra={"status_code": response.status_code, "body": response.text[:500]},
        )
        return {"results": [], "query": query, "error": response.text[:200]}
    return response.json()


class TavilyClient:
    """Tavily search API (POST). Retries are applied only to this client instance."""

    def __init__(self, api_key: str | None, tool: ToolClient) -> None:
        self.api_key = api_key
        self._tool = tool

    async def search(self, query: str, *, max_results: int = 5) -> dict[str, Any]:
        if not self.api_key:
            logger.info("tavily_skipped", extra={"reason": "missing_api_key"})
            return {"results": [], "query": query}
        return await _tavily_search_traced(
            self._tool,
            self.api_key,
            query,
            max_results=max_results,
        )
