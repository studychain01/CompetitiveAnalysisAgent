from __future__ import annotations

import json
import logging
import sys
from datetime import UTC, datetime
from typing import Any

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
        return json.dumps(payload, default=str)


def configure_logging(level: str = "INFO") -> None:
    root = logging.getLogger()
    root.handlers.clear()
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonLogFormatter())
    root.addHandler(handler)
    root.setLevel(getattr(logging, level.upper(), logging.INFO))
