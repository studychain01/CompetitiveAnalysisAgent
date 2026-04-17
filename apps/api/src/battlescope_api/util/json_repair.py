from __future__ import annotations

import json
import re
from typing import Any


def strip_markdown_json_fence(text: str) -> str:
    stripped = text.strip()
    if not stripped.startswith("```"):
        return stripped
    stripped = re.sub(r"^```(?:json)?\s*", "", stripped, flags=re.IGNORECASE)
    stripped = re.sub(r"\s*```$", "", stripped)
    return stripped.strip()


def extract_json_object(text: str) -> str | None:
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        return None
    return text[start : end + 1]


def parse_llm_json(text: str) -> dict[str, Any]:
    """
    Parse JSON objects from LLM output: strip ```json fences, then try full parse,
    then fall back to the outermost {...} slice.
    """
    raw = strip_markdown_json_fence(text)
    try:
        value: Any = json.loads(raw)
    except json.JSONDecodeError:
        candidate = extract_json_object(raw)
        if candidate is None:
            raise
        value = json.loads(candidate)
    if not isinstance(value, dict):
        msg = f"expected JSON object, got {type(value).__name__}"
        raise TypeError(msg)
    return value
