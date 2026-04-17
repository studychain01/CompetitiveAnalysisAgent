from __future__ import annotations

import json
from typing import Any

from langsmith import traceable

from battlescope_api.tools.tool_client import ToolClient
from battlescope_api.util.json_repair import parse_llm_json


class AssistantJsonParseError(ValueError):
    """HTTP 200 from OpenAI, but ``message.content`` was not a JSON object."""

    def __init__(self, assistant_text: str) -> None:
        super().__init__("OpenAI assistant content was not parseable as a JSON object")
        self.assistant_text = assistant_text


def _llm_trace_inputs(inputs: dict) -> dict:
    """Do not log secrets or full prompts; LangSmith gets a safe preview."""
    system = inputs.get("system") or ""
    user = inputs.get("user") or ""
    preview_len = 1500

    def _preview(text: str) -> str:
        if len(text) <= preview_len:
            return text
        return text[:preview_len] + "…<truncated>"

    return {
        "model": inputs.get("model"),
        "temperature": inputs.get("temperature"),
        "base_url": inputs.get("base_url"),
        "api_key_configured": bool(inputs.get("api_key")),
        "system_preview": _preview(system) if isinstance(system, str) else "",
        "user_preview": _preview(user) if isinstance(user, str) else "",
    }


@traceable(
    name="openai_chat_json",
    run_type="llm",
    process_inputs=_llm_trace_inputs,
)
async def _openai_complete_json_traced(
    tool: ToolClient,
    api_key: str,
    base_url: str,
    default_model: str,
    system: str,
    user: str,
    *,
    model: str | None,
    temperature: float,
) -> dict[str, Any]:
    url = f"{base_url.rstrip('/')}/v1/chat/completions"
    payload: dict[str, Any] = {
        "model": model or default_model,
        "temperature": temperature,
        "response_format": {"type": "json_object"},
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
    }
    response = await tool.request(
        "POST",
        url,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        json=payload,
    )
    response.raise_for_status()
    data = response.json()
    content = data["choices"][0]["message"]["content"]
    if not isinstance(content, str):
        msg = "OpenAI returned non-string message content"
        raise TypeError(msg)
    try:
        return parse_llm_json(content)
    except (json.JSONDecodeError, TypeError, ValueError) as exc:
        raise AssistantJsonParseError(content, cause=exc) from exc


class LLMClient:
    """OpenAI-compatible chat completions with JSON object output (httpx, no SDK)."""

    def __init__(
        self,
        api_key: str | None,
        tool: ToolClient,
        *,
        base_url: str = "https://api.openai.com",
        default_model: str = "gpt-4o-mini",
    ) -> None:
        self.api_key = api_key
        self._tool = tool
        self.base_url = base_url.rstrip("/")
        self.default_model = default_model

    async def complete_json(
        self,
        system: str,
        user: str,
        *,
        model: str | None = None,
        temperature: float = 0.2,
    ) -> dict[str, Any]:
        if not self.api_key:
            raise RuntimeError("OPENAI_API_KEY is not configured")
        return await _openai_complete_json_traced(
            self._tool,
            self.api_key,
            self.base_url,
            self.default_model,
            system,
            user,
            model=model,
            temperature=temperature,
        )
