"""
Presentation: API Config

Reads configuration from environment variables / .env file.
Pydantic-settings v2 used for type-safe config loading.
Keys are never validated at startup — validation happens at first use.
"""
from __future__ import annotations

from typing import Any, Literal
from pathlib import Path
import secrets

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # LLM provider keys
    gemini_api_key: str = ""
    openai_api_key: str = ""
    anthropic_api_key: str = ""
    
    # Vertex AI configuration
    google_cloud_project: str | None = None
    google_cloud_location: str = "europe-west1"

    # Runtime defaults (Can be overridden by DEFAULT_PROVIDER, DEFAULT_MODEL)
    default_provider: str = "gemini"
    default_model: str = "gemini-3.6-flash"

    # RAG (Can be overridden by RAG_TOP_K and RAG_MIN_SCORE)
    rag_top_k: int = 5
    rag_min_score: float = 0.30

    # Multi-Agent Debate Internal Review (Can be overridden by REVIEW_ROUNDS)
    review_rounds: int = 1

    # Storage paths (relative to backend/ directory)
    vault_root: Path = Path("../obsidian_vault")
    chroma_persist_dir: Path = Path(".chroma")
    sqlite_db_path: Path = Path("atenea.db")
    chroma_host: str | None = None
    chroma_port: int = 8000

    # Server
    cors_origins: list[str] = ["http://localhost:5173", "http://localhost:4173"]
    api_version: str = "0.4.0"

    # Learning Agent file size limit (MB)
    max_learn_file_mb: int = 50

    # Image Generation (Fidias - "imagen" | "")
    image_generation_provider: str = ""

    # Audio Integration (Phase 5)
    whisper_model: str = "base"
    whisper_language: str = "es"
    whisper_beam_size: int = 1
    whisper_threads: int = 4
    whisper_initial_prompt: str = (
        "Conversación técnica en castellano sobre desarrollo de software, arquitectura de sistemas e infraestructura. "
        "Uso frecuente de términos técnicos, herramientas, patrones y nombres en inglés: "
        "backend, frontend, fullstack, microservicios, API REST, GraphQL, WebSocket, gRPC, "
        "Docker, Kubernetes, CI/CD, DevOps, DevSecOps, cloud-native, serverless, AWS, Azure, GCP, "
        "SQLite, PostgreSQL, Redis, Kafka, ChromaDB, FastAPI, Python, TypeScript, JavaScript, Vue, React, "
        "Node.js, Next.js, Vite, CQRS, Event-Driven, DDD, clean architecture, arquitectura hexagonal, "
        "Zero-Trust, STRIDE, SPOF, Langfuse, OpenTelemetry, Prometheus, Grafana, HITL, Pull Request, "
        "merge, commit, branch, deploy, clúster, endpoints, logs, métricas, tracing."
    )
    kokoro_model_path: Path = Path("voices/kokoro-v1.0.onnx")
    kokoro_voices_path: Path = Path("voices/voices-v1.0.bin")
    kokoro_voice_name: str = "ef_dora"
    kokoro_omp_num_threads: int | None = None

    # Observability (Phase 6 / Langfuse)
    langfuse_metrics_enabled: bool = False
    langfuse_public_key: str = ""
    langfuse_secret_key: str = ""
    langfuse_host: str = "http://localhost:3000"
    langfuse_base_url: str = ""
    langfuse_default_user_id: str = "local_user"

    # Authentication & Security (Phase 7)
    auth_secret_key: str = Field(default_factory=lambda: secrets.token_urlsafe(48))
    auth_token_expiry_seconds: int = 28800
    auth_cookie_secure: bool = False
    auth_cookie_name: str = "atenea_session"
    auth_cookie_samesite: Literal["lax", "strict", "none"] = "lax"
    auth_delete_strategy: Literal["soft", "hard"] = "soft"
    database_url: str = ""
    initial_setup_token: str | None = None
    auth_trust_x_forwarded_for: bool = False
    auth_rate_limit_login_attempts: int = 5
    auth_rate_limit_login_window_seconds: int = 60
    auth_rate_limit_setup_attempts: int = 3
    auth_rate_limit_setup_window_seconds: int = 60

    @property
    def effective_langfuse_host(self) -> str:
        return self.langfuse_base_url or self.langfuse_host or "http://localhost:3000"

    model_config = SettingsConfigDict(
        env_file=(".env", "../.env"),
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

    def model_post_init(self, __context: Any) -> None:
        if self.auth_cookie_samesite == "none" and not self.auth_cookie_secure:
            raise ValueError("auth_cookie_secure must be True when auth_cookie_samesite is set to 'none'")



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
