from __future__ import annotations

import json
import logging

from battlescope_api.log_setup import JsonLogFormatter, configure_logging


def test_configure_logging_emits_json_lines(capsys) -> None:
    root = logging.getLogger()
    old_handlers = list(root.handlers)
    old_level = root.level
    try:
        configure_logging("INFO")
        logging.getLogger("test_logger").warning("hello", extra={"run_id": "run-1"})
        captured = capsys.readouterr().out.strip().splitlines()
        assert captured
        payload = json.loads(captured[-1])
        assert payload["level"] == "WARNING"
        assert payload["logger"] == "test_logger"
        assert payload["msg"] == "hello"
        assert payload["run_id"] == "run-1"
    finally:
        root.handlers[:] = old_handlers
        root.setLevel(old_level)


def test_json_log_formatter_includes_extras() -> None:
    logger = logging.getLogger("fmt.test")
    record = logger.makeRecord(
        name=logger.name,
        level=logging.INFO,
        fn=__file__,
        lno=1,
        msg="m",
        args=(),
        exc_info=None,
        func=None,
        extra={"trace_id": "t-1"},
        sinfo=None,
    )
    line = JsonLogFormatter().format(record)
    payload = json.loads(line)
    assert payload["trace_id"] == "t-1"


def test_json_log_formatter_truncates_long_extra_strings() -> None:
    logger = logging.getLogger("fmt.test.big")
    blob = "x" * 5000
    record = logger.makeRecord(
        name=logger.name,
        level=logging.INFO,
        fn=__file__,
        lno=1,
        msg="short",
        args=(),
        exc_info=None,
        func=None,
        extra={"packed": blob},
        sinfo=None,
    )
    line = JsonLogFormatter().format(record)
    payload = json.loads(line)
    assert payload["msg"] == "short"
    assert "omitted" in payload["packed"]
    assert len(payload["packed"]) < len(blob)
