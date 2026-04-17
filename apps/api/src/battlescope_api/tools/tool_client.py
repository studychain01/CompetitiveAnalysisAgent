from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

import httpx

from battlescope_api.settings import Settings, get_settings
from battlescope_api.tools.http_client import create_http_client

logger = logging.getLogger(__name__)

IDEMPOTENT_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})
RETRYABLE_STATUS = frozenset({429, 500, 502, 503, 504})
RETRYABLE_EXCEPTIONS: tuple[type[BaseException], ...] = (
    httpx.TimeoutException,
    httpx.ConnectError,
    httpx.ReadError,
    httpx.WriteError,
    httpx.RemoteProtocolError,
)


class ToolClient:
    """
    HTTP wrapper with retries for idempotent reads (Tavily/Firecrawl-style GETs).

    Policy: up to ``max_retries`` *re-attempts* after the first try (plan: max 2 retries → 3 tries).
    """

    def __init__(
        self,
        client: httpx.AsyncClient,
        *,
        max_retries: int = 2,
        backoff_base_s: float = 0.4,
        retryable_methods: frozenset[str] | None = None,
    ) -> None:
        self._client = client
        self.max_retries = max_retries
        self.backoff_base_s = backoff_base_s
        self.retryable_methods = retryable_methods or IDEMPOTENT_METHODS

    def _sleep_s(self, attempt: int, response: httpx.Response | None) -> float:
        if response is not None and response.status_code == 429:
            retry_after = response.headers.get("Retry-After")
            if retry_after:
                try:
                    return float(retry_after)
                except ValueError:
                    pass
        return self.backoff_base_s * (2**attempt)

    def _log_retry(
        self,
        *,
        reason: str,
        method: str,
        url: str,
        attempt: int,
        sleep_s: float,
        status_code: int | None = None,
        exc_type: str | None = None,
    ) -> None:
        payload = {
            "reason": reason,
            "method": method,
            "url": url,
            "attempt": attempt,
            "sleep_s": sleep_s,
            "status_code": status_code,
            "exc_type": exc_type,
        }
        logger.warning("tool_client_retry %s", json.dumps(payload, default=str))

    async def request(self, method: str, url: str, **kwargs: Any) -> httpx.Response:
        method_u = method.upper()
        for attempt in range(self.max_retries + 1):
            try:
                response = await self._client.request(method, url, **kwargs)
                if (
                    response.status_code in RETRYABLE_STATUS
                    and method_u in self.retryable_methods
                    and attempt < self.max_retries
                ):
                    sleep_s = self._sleep_s(attempt, response)
                    self._log_retry(
                        reason="http_status",
                        method=method_u,
                        url=url,
                        attempt=attempt,
                        sleep_s=sleep_s,
                        status_code=response.status_code,
                    )
                    await asyncio.sleep(sleep_s)
                    continue
                return response
            except RETRYABLE_EXCEPTIONS as exc:
                if method_u not in self.retryable_methods or attempt >= self.max_retries:
                    raise
                sleep_s = self._sleep_s(attempt, None)
                self._log_retry(
                    reason="exception",
                    method=method_u,
                    url=url,
                    attempt=attempt,
                    sleep_s=sleep_s,
                    exc_type=type(exc).__name__,
                )
                await asyncio.sleep(sleep_s)


def create_tool_client(**kwargs: Any) -> ToolClient:
    return ToolClient(create_http_client(), **kwargs)


def create_tool_client_from_settings(settings: Settings | None = None) -> ToolClient:
    resolved = settings or get_settings()
    return ToolClient(
        create_http_client(),
        max_retries=resolved.http_max_retries,
        backoff_base_s=resolved.http_backoff_base_s,
    )
