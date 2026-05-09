"""Typed configuration loaded from `.env`.

Defaults match `.env.example`. Missing required tokens raise at first access
rather than at import, so test/dev workflows that do not exercise external
services do not need a fully populated `.env`.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


REPO_ROOT = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=REPO_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=True,
    )

    # OpenRouter
    OPENROUTER_API_KEY: SecretStr = SecretStr("")
    OPENROUTER_BASE_URL: str = "https://openrouter.ai/api/v1"

    GUARD_MODEL: str = "anthropic/claude-haiku-4.5"
    MATCHER_MODEL: str = "anthropic/claude-haiku-4.5"
    GENERATOR_MODEL: str = "deepseek/deepseek-chat-v3"
    README_MODEL: str = "anthropic/claude-haiku-4.5"

    # GitHub
    GITHUB_TOKEN: SecretStr = SecretStr("")
    GITHUB_ORG: str = "vibemill-apps"

    # Vercel
    VERCEL_TOKEN: SecretStr = SecretStr("")
    VERCEL_TEAM_ID: str = ""

    # Supabase
    SUPABASE_URL: str = ""
    SUPABASE_SERVICE_ROLE_KEY: SecretStr = SecretStr("")

    # Resend (V1+)
    RESEND_API_KEY: SecretStr = SecretStr("")
    RESEND_FROM_ADDRESS: str = "mill@vibemill.dev"

    # Local config
    VIBEMILL_PATH: Path = Path("/home/ian/vibemill")
    SQLITE_PATH: Path = Path("/home/ian/vibemill/data/vibemill.sqlite")
    LOG_LEVEL: str = "INFO"

    # Spending guardrail (USD)
    DAILY_COST_CAP_USD: float = 5.00

    # Live app cap
    LIVE_APP_CAP: int = 100

    # Viral thresholds
    VIRAL_VIEWS_PER_DAY: int = 10_000
    VIRAL_CONCURRENT_USERS: int = 2_000

    @property
    def repo_root(self) -> Path:
        return REPO_ROOT

    @property
    def prompts_dir(self) -> Path:
        return REPO_ROOT / "prompts"

    @property
    def archetypes_dir(self) -> Path:
        return REPO_ROOT / "archetypes"

    @property
    def migrations_sqlite_dir(self) -> Path:
        return REPO_ROOT / "migrations" / "sqlite"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
