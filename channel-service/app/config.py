"""
Channel Service Configuration.

Minimal config — only needs the CRM callback URL to send delivery receipts.
"""

from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    """Channel service settings."""

    # ── CRM Callback URL ──
    CRM_RECEIPT_URL: str = "http://localhost:8000/api/receipts"

    # ── App Settings ──
    APP_NAME: str = "Xeno Channel Service"
    DEBUG: bool = False

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "case_sensitive": True,
    }


@lru_cache()
def get_settings() -> Settings:
    """Return cached settings instance."""
    return Settings()
