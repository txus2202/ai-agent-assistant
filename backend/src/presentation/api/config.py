"""
Presentation: API Config

Reads configuration from environment variables / .env file.
Pydantic-settings v2 used for type-safe config loading.
Keys are never validated at startup — validation happens at first use.
"""
from __future__ import annotations

from pathlib import Path

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # LLM provider keys
    gemini_api_key: str = ""
    openai_api_key: str = ""
    anthropic_api_key: str = ""

    # Runtime defaults (Can be overridden by DEFAULT_PROVIDER, DEFAULT_MODEL)
    default_provider: str = "gemini"
    default_model: str = "gemini-1.5-flash"

    # RAG (Can be overridden by RAG_TOP_K)
    rag_top_k: int = 5

    # Storage paths (relative to backend/ directory)
    vault_root: Path = Path("../obsidian_vault")
    chroma_persist_dir: Path = Path(".chroma")
    sqlite_db_path: Path = Path("atenea.db")

    # Server
    cors_origins: list[str] = ["http://localhost:5173", "http://localhost:4173"]
    api_version: str = "0.4.0"

    # Learning Agent file size limit (MB)
    max_learn_file_mb: int = 50

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    @field_validator("default_provider")
    @classmethod
    def validate_provider(cls, v: str) -> str:
        allowed = {"gemini", "openai", "anthropic"}
        if v not in allowed:
            raise ValueError(f"Unknown provider: '{v}'. Must be one of {allowed}")
        return v


# Module-level singleton — replaced in tests via dependency override
_settings: Settings | None = None


def get_settings() -> Settings:
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings


def reset_settings() -> None:
    """Reset the cached singleton. Used in tests."""
    global _settings
    _settings = None
