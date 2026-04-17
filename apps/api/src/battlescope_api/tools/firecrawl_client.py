from __future__ import annotations

import logging
from typing import Any

from langsmith import traceable

from battlescope_api.tools.tool_client import ToolClient

logger = logging.getLogger(__name__)

FIRECRAWL_SCRAPE_URL = "https://api.firecrawl.dev/v1/scrape"


def _firecrawl_trace_inputs(inputs: dict) -> dict:
    return {
        "url": inputs.get("url"),
        "api_key_configured": bool(inputs.get("api_key")),
    }


@traceable(
    name="firecrawl_scrape",
    run_type="tool",
    process_inputs=_firecrawl_trace_inputs,
)
async def _firecrawl_scrape_traced(
    tool: ToolClient,
    api_key: str,
    url: str,
) -> dict[str, Any]:
    body = {
        "url": url,
        "formats": ["markdown"],
        "onlyMainContent": True,
    }
    response = await tool.request(
        "POST",
        FIRECRAWL_SCRAPE_URL,
        json=body,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
    )
    if response.status_code >= 400:
        logger.warning(
            "firecrawl_http_error",
            extra={"status_code": response.status_code, "body": response.text[:500]},
        )
        return {"success": False, "error": response.text[:300]}
    return response.json()


class FirecrawlClient:
    """Firecrawl scrape API (POST)."""

    def __init__(self, api_key: str | None, tool: ToolClient) -> None:
        self.api_key = api_key
        self._tool = tool

    async def scrape_url(self, url: str) -> dict[str, Any]:
        if not self.api_key:
            logger.info("firecrawl_skipped", extra={"reason": "missing_api_key"})
            return {"success": False, "error": "missing_api_key"}
        return await _firecrawl_scrape_traced(self._tool, self.api_key, url)
