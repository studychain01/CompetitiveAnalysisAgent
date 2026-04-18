"""Tests for optional ``risk_theme_categories`` / ``risk_theme_headlines`` parallel to bullets."""

from battlescope_api.graph.nodes.sec_risk import (
    validated_risk_theme_categories,
    validated_risk_theme_headlines,
)


def test_validated_categories_requires_same_length() -> None:
    assert validated_risk_theme_categories(["a", "b"], ["Competition"]) is None
    assert validated_risk_theme_categories(["a"], ["x", "y"]) is None


def test_validated_categories_empty_inputs() -> None:
    assert validated_risk_theme_categories([], []) is None
    assert validated_risk_theme_categories(["a"], None) is None
    assert validated_risk_theme_categories(["a"], []) is None


def test_validated_categories_normalizes_case_and_unknown() -> None:
    out = validated_risk_theme_categories(
        ["bullet one", "bullet two"],
        ["competition", "made up label"],
    )
    assert out == ["Competition", "Other"]


def test_validated_categories_rejects_empty_label() -> None:
    assert validated_risk_theme_categories(["a"], ["  "]) is None


def test_validated_headlines_requires_same_length() -> None:
    assert validated_risk_theme_headlines(["a", "b"], ["h1"]) is None


def test_validated_headlines_rejects_empty() -> None:
    assert validated_risk_theme_headlines(["a"], ["  "]) is None


def test_validated_headlines_truncates_long() -> None:
    long_h = "word " * 40
    out = validated_risk_theme_headlines(["a"], [long_h])
    assert out is not None
    assert len(out[0]) <= 120
    assert out[0].endswith("…")
