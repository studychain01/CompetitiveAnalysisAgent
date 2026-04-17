from __future__ import annotations

import json
from pathlib import Path

import pytest

from battlescope_api.util.json_repair import parse_llm_json


def test_parse_llm_json_strips_fence_and_parses(fixtures_dir: Path) -> None:
    text = (fixtures_dir / "llm_profile_with_fence.txt").read_text(encoding="utf-8")
    data = parse_llm_json(text)
    assert data["category"] == "venue booking software"
    assert data["competitor_seeds"] == ["RivalA", "RivalB"]


def test_parse_llm_json_extracts_object_with_preamble() -> None:
    text = 'Noise...\n{"a": 1, "b": "two"}\ntrailing'
    assert parse_llm_json(text) == {"a": 1, "b": "two"}


def test_parse_llm_json_rejects_non_object() -> None:
    with pytest.raises(TypeError):
        parse_llm_json("[1, 2, 3]")


def test_tavily_fixture_is_valid_json(fixtures_dir: Path) -> None:
    raw = (fixtures_dir / "tavily_search_response.json").read_text(encoding="utf-8")
    payload = json.loads(raw)
    assert payload["results"][0]["url"].startswith("https://")


def test_markdown_fixture_loads(fixtures_dir: Path) -> None:
    md = (fixtures_dir / "competitor_page.md").read_text(encoding="utf-8")
    assert "ExampleCo" in md
    assert "Pricing" in md
