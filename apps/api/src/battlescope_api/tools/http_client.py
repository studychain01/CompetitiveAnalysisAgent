import httpx

# Retrying wrapper: ``battlescope_api.tools.tool_client.ToolClient``.


def create_http_client() -> httpx.AsyncClient:
    """
    Shared async HTTP client with sane timeouts for Tavily/Firecrawl/raw fetch fallbacks.
    Pair with :class:`ToolClient` for retry/backoff on idempotent requests.
    """
    timeout = httpx.Timeout(30.0, connect=10.0)
    return httpx.AsyncClient(timeout=timeout, follow_redirects=True)
