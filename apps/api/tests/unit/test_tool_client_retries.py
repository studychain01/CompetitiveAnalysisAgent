from __future__ import annotations

import httpx
import pytest

from battlescope_api.tools.tool_client import ToolClient


@pytest.mark.asyncio
async def test_get_retries_on_429_then_succeeds() -> None:
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        if calls["n"] < 3:
            return httpx.Response(429, headers={"Retry-After": "0.01"}, request=request)
        return httpx.Response(200, json={"ok": True}, request=request)

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport, base_url="https://example.test") as client:
        tc = ToolClient(client, max_retries=2, backoff_base_s=0.01)
        response = await tc.request("GET", "/resource")

    assert response.status_code == 200
    assert response.json() == {"ok": True}
    assert calls["n"] == 3


@pytest.mark.asyncio
async def test_get_retries_on_read_timeout_then_succeeds() -> None:
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        if calls["n"] == 1:
            raise httpx.ReadTimeout("timeout", request=request)
        return httpx.Response(200, json={"recovered": True}, request=request)

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport, base_url="https://example.test") as client:
        tc = ToolClient(client, max_retries=2, backoff_base_s=0.01)
        response = await tc.request("GET", "/slow")

    assert response.status_code == 200
    assert response.json() == {"recovered": True}
    assert calls["n"] == 2


@pytest.mark.asyncio
async def test_post_does_not_retry_on_429() -> None:
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        return httpx.Response(429, request=request)

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport, base_url="https://example.test") as client:
        tc = ToolClient(client, max_retries=2, backoff_base_s=0.01)
        response = await tc.request("POST", "/mutate", json={"a": 1})

    assert response.status_code == 429
    assert calls["n"] == 1
