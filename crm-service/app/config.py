"""
CRM Service Configuration.

Loads environment variables with pydantic-settings for type safety
and validation. All required config is declared here — if a required
variable is missing, the app will fail fast on startup with a clear error.
"""

from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # ── Database ──
    DATABASE_URL: str = "postgresql://postgres:postgres@localhost:5432/xeno_crm"

    # ── Redis ──
    REDIS_URL: str = "redis://localhost:6379"

    # ── LLM API Keys ──
    GEMINI_API_KEY: str = ""
    GROQ_API_KEY: str = ""

    # ── Service URLs ──
    CHANNEL_SERVICE_URL: str = "http://localhost:8001/api/send"
    FRONTEND_URL: str = "http://localhost:5173"

    # ── App Settings ──
    APP_NAME: str = "Xeno AI CRM"
    DEBUG: bool = False

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "case_sensitive": True,
    }


@lru_cache()
def get_settings() -> Settings:
    """
    Return cached settings instance.
    Using lru_cache ensures we only parse env vars once.
    """
    return Settings()
