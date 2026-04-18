from __future__ import annotations

import json
import logging
import sys
from datetime import UTC, datetime
from typing import Any

# Cap single string fields in JSON logs so prompts / payloads do not print as one huge line.
_LOG_STRING_SOFT_MAX = 2400
_LOG_STRING_HEAD = 1600
_LOG_STRING_TAIL = 500


def _sanitize_log_value(value: Any, *, soft_max: int, head: int, tail: int) -> Any:
    """Shorten very long strings for JSON log lines; recurse into dicts and lists."""

    if isinstance(value, str):
        if len(value) <= soft_max:
            return value
        omitted = len(value) - head - tail
        if omitted <= 0:
            return value[:soft_max] + "\n...[truncated for log readability]..."
        bridge = f"\n...[omitted {omitted} characters for log readability]...\n"
        return value[:head] + bridge + value[-tail:]
    if isinstance(value, dict):
        return {k: _sanitize_log_value(v, soft_max=soft_max, head=head, tail=tail) for k, v in value.items()}
    if isinstance(value, list):
        return [_sanitize_log_value(v, soft_max=soft_max, head=head, tail=tail) for v in value]
    if isinstance(value, tuple):
        return tuple(_sanitize_log_value(v, soft_max=soft_max, head=head, tail=tail) for v in value)
    return value


def _standard_log_record_keys() -> frozenset[str]:
    record = logging.LogRecord(
        name="n",
        level=logging.INFO,
        pathname="p",
        lineno=1,
        msg="m",
        args=(),
        exc_info=None,
    )
    return frozenset(record.__dict__.keys())


_LOG_RECORD_STANDARD_ATTRS: frozenset[str] = _standard_log_record_keys()


class JsonLogFormatter(logging.Formatter):
    """One JSON object per line for easy ingestion."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "ts": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)
        for key, value in record.__dict__.items():
            if key in _LOG_RECORD_STANDARD_ATTRS or key.startswith("_"):
                continue
            payload[key] = value
        payload = _sanitize_log_value(
            payload,
            soft_max=_LOG_STRING_SOFT_MAX,
            head=_LOG_STRING_HEAD,
            tail=_LOG_STRING_TAIL,
        )
        return json.dumps(payload, default=str, ensure_ascii=False)


def configure_logging(level: str = "INFO") -> None:
    root = logging.getLogger()
    root.handlers.clear()
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonLogFormatter())
    root.addHandler(handler)
    resolved = getattr(logging, level.upper(), logging.INFO)
    root.setLevel(resolved)

    # Keep wire-level HTTP / SDK chatter off INFO so one-line JSON logs stay scannable.
    for name in (
        "httpx",
        "httpcore",
        "httpcore.http11",
        "httpcore.connection",
        "openai",
        "langchain_core",
        "langchain_openai",
        "langgraph",
    ):
        logging.getLogger(name).setLevel(logging.WARNING)
