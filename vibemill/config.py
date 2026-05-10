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
    GENERATOR_MODEL: str = "deepseek/deepseek-chat-v3"  # legacy single-model knob; rotation pool below supersedes
    README_MODEL: str = "anthropic/claude-haiku-4.5"  # used only when README_ROTATION_MODE=fixed

    # Generator + README model rotation. See vibemill/model_rotation.py and
    # OPERATIONS.md "Generator substrate composition". Three parallel
    # comma-separated lists; lengths must match. Weights must sum to 1.0.
    # Reasoning efforts: disabled | low | medium | high.
    GENERATOR_MODELS: str = "deepseek/deepseek-chat-v3"
    GENERATOR_WEIGHTS: str = "1.0"
    GENERATOR_REASONING_EFFORTS: str = "disabled"
    README_ROTATION_MODE: str = "match_generator"  # match_generator | fixed
    MAX_OUTPUT_PRICE_USD_PER_M: float = 2.00

    # DEPRECATED in v0.5: superseded by the three-tier output calibration
    # (see vibemill/tiers.py). The banger tier (~8%) replaces the
    # committed-path mechanism. These vars are no longer read by the
    # orchestrator; left here only so existing .env files don't trip
    # pydantic-settings strict-extra checks (extra='ignore' would handle
    # that anyway, but keeping them documented avoids confusion).
    COMMITTED_PATH_PROBABILITY: float = 0.07
    COMMITTED_PATH_BUILD_ATTEMPTS: int = 4
    COMMITTED_PATH_ARTICLE_CHARS: int = 2000

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

    # Spending guardrail (USD). Default tightened in v0.5 to accommodate
    # the three-tier output calibration (slop ~$0.05, mean_good ~$0.30,
    # banger ~$0.70) at 5 ships/day with banger-tier headroom.
    DAILY_COST_CAP_USD: float = 3.00

    # Web search (used by tier 2/3 generations to ground in real data).
    # Provider modules live in clients/. tavily is the default; setting
    # a different provider requires a corresponding clients/<provider>.py
    # module and a branch in web_search._dispatch.
    WEB_SEARCH_PROVIDER: str = "tavily"
    WEB_SEARCH_API_KEY: SecretStr = SecretStr("")
    WEB_SEARCH_MAX_QUERIES: int = 6  # ceiling; per-tier cap is the binding limit

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
