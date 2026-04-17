from __future__ import annotations

import logging
from typing import Any
from urllib.parse import urlencode

from battlescope_api.tools.tool_client import ToolClient

logger = logging.getLogger(__name__)

FMP_STABLE_BASE = "https://financialmodelingprep.com/stable"


class FinancialModelingPrepClient:
    """Financial Modeling Prep stable API (SEC filings search, etc.)."""

    def __init__(self, api_key: str | None, tool: ToolClient) -> None:
        self.api_key = api_key
        self._tool = tool

    async def sec_filings_search_by_symbol(
        self,
        symbol: str,
        *,
        date_from: str,
        date_to: str,
        page: int = 0,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """
        Return filing rows for ``symbol`` between ``date_from`` and ``date_to`` (YYYY-MM-DD).

        See FMP stable endpoint ``/sec-filings-search/symbol``.
        """
        if not self.api_key:
            logger.info("fmp_skipped", extra={"reason": "missing_api_key"})
            return []
        sym = (symbol or "").strip().upper()
        if not sym:
            return []
        params = {
            "symbol": sym,
            "from": date_from,
            "to": date_to,
            "page": str(page),
            "limit": str(limit),
            "apikey": self.api_key,
        }
        url = f"{FMP_STABLE_BASE}/sec-filings-search/symbol?{urlencode(params)}"
        response = await self._tool.request("GET", url)
        if response.status_code >= 400:
            logger.warning(
                "fmp_http_error",
                extra={"status_code": response.status_code, "body": response.text[:300]},
            )
            return []
        try:
            data: Any = response.json()
        except Exception as exc:
            logger.warning("fmp_json_error", extra={"error": str(exc)})
            return []
        if isinstance(data, dict) and data.get("Error Message"):
            logger.warning("fmp_api_error", extra={"message": str(data.get("Error Message"))[:200]})
            return []
        if not isinstance(data, list):
            return []
        return [x for x in data if isinstance(x, dict)]
