# config/settings.py
"""
Centralised application settings via pydantic-settings.

CHANGES FROM ORIGINAL
----------------------
Added:
  - database_url   : SQLAlchemy connection string for Postgres
                     (was database_path for SQLite)
  - redis_url      : Redis connection string for CacheManager
  - database_path  : kept for local SQLite fallback during development

Both database_url and database_path are optional with sensible defaults
so the app still boots locally without Docker.
"""

import os
from functools import lru_cache
from pydantic_settings import BaseSettings


class Settings(BaseSettings):

    # ── Azure OpenAI ─────────────────────────────────────────────────────────
    azure_openai_api_key: str
    azure_openai_endpoint: str
    openai_api_version: str
    azure_openai_chat_deployment_name: str

    # ── Azure OpenAI Embeddings (optional) ───────────────────────────────────
    azure_openai_embedding_deployment_name: str = ""

    # ── Database ─────────────────────────────────────────────────────────────
    # database_url: Full SQLAlchemy URL — used by ConnectionManager (Postgres)
    #   Set via DATABASE_URL env var (injected by docker-compose)
    #   Example: postgresql+psycopg2://postgres:pass@postgres_db:5432/interview_db
    #
    # database_path: Legacy SQLite path — used by SQLite repositories
    #   Falls back to local file for development outside Docker
    database_url: str = ""
    database_path: str = "database.db"

    # ── Redis ─────────────────────────────────────────────────────────────────
    # Set via REDIS_URL env var (injected by docker-compose)
    # Falls back to empty string — CacheManager handles the missing case
    redis_url: str = ""

    # ── Azure Storage (optional) ──────────────────────────────────────────────
    azure_storage_connection_string: str = ""
    azure_storage_container_name: str = ""

    # ── Server ────────────────────────────────────────────────────────────────
    host: str = "127.0.0.1"
    port: int = 8000

    # ── Pipeline ──────────────────────────────────────────────────────────────
    token_alert_threshold: int = 80000
    llm_temperature: float = 0.0

    # ── App metadata ─────────────────────────────────────────────────────────
    app_title: str = "AI Interview Feedback Pipeline Server"
    app_version: str = "1.0.0"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False


@lru_cache()
def get_settings() -> Settings:
    """
    Returns a cached Settings instance.

    lru_cache ensures Settings() is only instantiated once per process —
    effectively a Singleton for configuration. Every call to get_settings()
    returns the exact same object.
    """
    return Settings()
