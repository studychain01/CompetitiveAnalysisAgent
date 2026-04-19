import logging
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv
from pydantic import AliasChoices, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from urllib.parse import urlparse

# ``settings.py`` -> ``battlescope_api`` -> ``src`` -> ``apps/api``
_API_ROOT = Path(__file__).resolve().parent.parent.parent
_ENV_FILE = _API_ROOT / ".env"

# LangSmith / LangChain read tracing vars from ``os.environ``. Pydantic only loads
# declared fields from ``.env``; this ensures ``LANGCHAIN_*`` / ``LANGSMITH_*`` in
# ``apps/api/.env`` are visible to langsmith without relying on shell cwd.
load_dotenv(_ENV_FILE, override=False)
# Monorepo users often keep secrets in the repo root ``.env``; load after ``apps/api/.env`` so
# per-service keys win when the same name exists in both files (``override=False``).
_REPO_ROOT_ENV = _API_ROOT.parent.parent / ".env"
if _REPO_ROOT_ENV.is_file():
    load_dotenv(_REPO_ROOT_ENV, override=False)

logger = logging.getLogger(__name__)

# SEC EDGAR: identify the client; ``user.invalid`` is reserved (RFC 2606) — override in production.
_DEFAULT_SEC_EDGAR_USER_AGENT = "BattleScope/1.0 (mailto:battlescope@user.invalid)"


def _looks_like_openai_platform_secret(key: str) -> bool:
    """Heuristic for keys sent to ``api.openai.com`` (not for Azure/custom proxies)."""
    if key.startswith("sk-proj-"):
        return len(key) >= 40
    if key.startswith("sk-"):
        return len(key) >= 40
    return False


def _secret_first_last_four(value: str | None) -> str:
    """Safe fingerprint for logs: first 4 + last 4, or status only if too short."""
    if not value:
        return "not_set"
    s = value
    if len(s) <= 8:
        return f"set(len={len(s)}, redacted)"
    return f"{s[:4]}…{s[-4:]} len={len(s)}"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(_ENV_FILE) if _ENV_FILE.exists() else ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    cors_origins: str = "http://localhost:3000"
    log_level: str = "INFO"
    http_max_retries: int = 2
    http_backoff_base_s: float = 0.4

    tavily_api_key: str | None = None
    newsapi_api_key: str | None = Field(
        default=None,
        validation_alias=AliasChoices(
            "NEWSAPI_API_KEY",
            "NEWS_API_API_KEY",
            "NEWSAPI_KEY",
            "NEWS_ORG_API_KEY",
        ),
    )
    firecrawl_api_key: str | None = None
    alphavantage_api_key: str | None = Field(
        default=None,
        validation_alias=AliasChoices("ALPHA_VANTAGE_API_KEY", "ALPHAVANTAGE_API_KEY"),
    )
    fmp_api_key: str | None = Field(
        default=None,
        validation_alias=AliasChoices("FMP_API_KEY", "FINANCIAL_MODELING_PREP_API_KEY"),
    )
    openai_api_key: str | None = None
    openai_base_url: str = "https://api.openai.com"
    openai_model: str = "gpt-4o-mini"
    intake_context_max_chars: int = 16_000
    # SEC EDGAR requests should identify the client; override in production with a real URL or email.
    sec_edgar_user_agent: str = _DEFAULT_SEC_EDGAR_USER_AGENT
    
    #chars that we read from 10K file, later on will stip 1A details before sending to LLM
    sec_risk_filing_download_max_chars: int = 800_000
    sec_risk_excerpt_max_chars: int = 200_000
    competitor_react_recursion_limit: int = 40
    competitor_context_max_chars: int = 200_000
    peer_react_recursion_limit: int = 40
    peer_research_context_max_chars: int = 100_000
    strategy_context_max_chars: int = 200_000
    strategy_allow_tavily_followup: bool = Field(
        default=False,
        validation_alias=AliasChoices("STRATEGY_TAVILY_FOLLOWUP", "strategy_allow_tavily_followup"),
    )

    @field_validator("strategy_allow_tavily_followup", mode="before")
    @classmethod
    def coerce_strategy_followup_bool(cls, value: object) -> bool:
        if value is None or value is False:
            return False
        if value is True:
            return True
        if isinstance(value, str):
            s = value.strip().lower()
            if s in ("0", "false", "no", "off", ""):
                return False
            return s in ("1", "true", "yes", "on")
        return bool(value)

    @field_validator(
        "tavily_api_key",
        "newsapi_api_key",
        "firecrawl_api_key",
        "alphavantage_api_key",
        "fmp_api_key",
        "openai_api_key",
        mode="before",
    )
    @classmethod
    def strip_secret_whitespace(cls, value: str | None) -> str | None:
        """Only trim leading/trailing whitespace — no quote or Bearer mangling."""
        if value is None or not isinstance(value, str):
            return None
        s = value.strip()
        return s or None

    @field_validator("openai_base_url", mode="before")
    @classmethod
    def strip_base_url(cls, value: str) -> str:
        if isinstance(value, str):
            return value.strip() or "https://api.openai.com"
        return value

    @field_validator("sec_edgar_user_agent", mode="before")
    @classmethod
    def strip_sec_user_agent(cls, value: str) -> str:
        if isinstance(value, str) and value.strip():
            return value.strip()
        return _DEFAULT_SEC_EDGAR_USER_AGENT

    @property
    def openai_sdk_base_url(self) -> str:
        """
        Base URL for ``langchain_openai.ChatOpenAI`` / the OpenAI SDK.

        The SDK posts to ``{base_url}/chat/completions``. Official OpenAI expects
        ``base_url`` to end with ``/v1``. Our httpx ``LLMClient`` instead appends
        ``/v1/chat/completions`` to a host-style ``OPENAI_BASE_URL``, so env files
        often set ``https://api.openai.com`` without ``/v1`` — normalize here.
        """
        raw = (self.openai_base_url or "").strip().rstrip("/")
        if not raw:
            return "https://api.openai.com/v1"
        parsed = urlparse(raw)
        path = (parsed.path or "").rstrip("/")
        if path in ("", "/"):
            return f"{raw}/v1"
        return raw


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    logger.info(
        "settings_loaded",
        extra={"openai_api_key_fingerprint": _secret_first_last_four(settings.openai_api_key)},
    )
    _k = settings.openai_api_key or ""
    _host = (urlparse(settings.openai_base_url).hostname or "").lower()
    if _k and _host in ("api.openai.com", "openai.com") and not _looks_like_openai_platform_secret(_k):
        logger.warning(
            "OPENAI_API_KEY does not look like a valid OpenAI platform secret "
            "(expected sk- or sk-proj- from https://platform.openai.com/api-keys). "
            "Chat completions will likely return 401.",
            extra={"openai_api_key_fingerprint": _secret_first_last_four(_k)},
        )
    return settings
