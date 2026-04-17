"""Tests for OpenAI base URL normalization (SDK vs httpx client conventions)."""

import pytest

from battlescope_api.settings import Settings, get_settings


@pytest.fixture
def clear_settings_cache():
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def test_openai_sdk_base_url_appends_v1_for_host_only(
    monkeypatch: pytest.MonkeyPatch, clear_settings_cache
) -> None:
    monkeypatch.setenv("OPENAI_BASE_URL", "https://api.openai.com")
    get_settings.cache_clear()
    s = get_settings()
    assert s.openai_sdk_base_url == "https://api.openai.com/v1"


def test_openai_sdk_base_url_unchanged_when_v1_present(
    monkeypatch: pytest.MonkeyPatch, clear_settings_cache
) -> None:
    monkeypatch.setenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
    get_settings.cache_clear()
    s = get_settings()
    assert s.openai_sdk_base_url == "https://api.openai.com/v1"


def test_openai_sdk_base_url_custom_path_unchanged(
    monkeypatch: pytest.MonkeyPatch, clear_settings_cache
) -> None:
    """Proxy/gateway URLs with a non-root path are passed through unchanged."""
    monkeypatch.setenv("OPENAI_BASE_URL", "https://gateway.example/proxy/openai")
    get_settings.cache_clear()
    s = get_settings()
    assert s.openai_sdk_base_url == "https://gateway.example/proxy/openai"


def test_openai_sdk_base_url_property_without_cache(
    monkeypatch: pytest.MonkeyPatch, clear_settings_cache
) -> None:
    monkeypatch.setenv("OPENAI_BASE_URL", "https://api.openai.com/")
    get_settings.cache_clear()
    s = Settings()
    assert s.openai_sdk_base_url == "https://api.openai.com/v1"
