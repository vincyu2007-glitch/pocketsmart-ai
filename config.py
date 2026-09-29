"""Application configuration loaded from environment variables / .env file."""

from __future__ import annotations

import os
import secrets
import warnings
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")


def _bool(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None or raw == "":
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _int(name: str, default: int) -> int:
    try:
        return int(str(os.getenv(name, default)).strip())
    except (TypeError, ValueError):
        return default


def _float(name: str, default: float) -> float:
    try:
        return float(str(os.getenv(name, default)).strip())
    except (TypeError, ValueError):
        return default


def _secret_key() -> str:
    key = os.getenv("SECRET_KEY", "").strip()
    if key and key != "change-me-to-a-long-random-string":
        return key
    generated = secrets.token_hex(32)
    warnings.warn(
        "SECRET_KEY is not configured. Generated an ephemeral key - sessions "
        "will not survive a restart. Set SECRET_KEY in .env for production.",
        RuntimeWarning,
        stacklevel=2,
    )
    return generated


class Config:
    """Base configuration shared by every environment."""

    BASE_DIR = BASE_DIR
    SECRET_KEY = _secret_key()

    DEBUG = _bool("FLASK_DEBUG", False)
    PORT = _int("PORT", 5000)
    ALLOW_GUEST = _bool("ALLOW_GUEST", False)
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = _bool("SESSION_COOKIE_SECURE", False)
    PERMANENT_SESSION_LIFETIME = _int("SESSION_LIFETIME_SECONDS", 60 * 60 * 12)

    # Google Gemini
    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "").strip()
    GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash").strip()
    GEMINI_TEMPERATURE = _float("GEMINI_TEMPERATURE", 0.4)
    GEMINI_MAX_OUTPUT_TOKENS = _int("GEMINI_MAX_OUTPUT_TOKENS", 8192)
    GEMINI_TIMEOUT = _int("GEMINI_TIMEOUT", 60)
    GEMINI_MAX_RETRIES = _int("GEMINI_MAX_RETRIES", 3)

    # Storage
    DATA_DIR = BASE_DIR / os.getenv("DATA_DIR", "data")
    DATABASE_PATH = BASE_DIR / os.getenv("DATABASE_PATH", "data/pocketsmart.db")

    # Uploads / images
    MAX_CONTENT_LENGTH = _int("MAX_CONTENT_LENGTH_MB", 8) * 1024 * 1024
    MAX_IMAGE_DIMENSION = _int("MAX_IMAGE_DIMENSION", 1600)

    @classmethod
    def as_dict(cls) -> dict:
        return {
            key: getattr(cls, key)
            for key in dir(cls)
            if key.isupper() and not key.startswith("_")
        }


class DevelopmentConfig(Config):
    DEBUG = True


class TestingConfig(Config):
    TESTING = True
    DEBUG = False
    ALLOW_GUEST = True
    GEMINI_API_KEY = ""
    DATA_DIR = BASE_DIR / "data" / "test"
    DATABASE_PATH = BASE_DIR / "data" / "test" / "pocketsmart_test.db"
    WTF_CSRF_ENABLED = False


class ProductionConfig(Config):
    SESSION_COOKIE_SECURE = _bool("SESSION_COOKIE_SECURE", True)
    SESSION_COOKIE_SAMESITE = "Lax"


CONFIGS = {
    "development": DevelopmentConfig,
    "testing": TestingConfig,
    "production": ProductionConfig,
    "default": DevelopmentConfig,
}


def get_config(name: str | None = None):
    key = (name or os.getenv("FLASK_ENV") or "default").lower()
    return CONFIGS.get(key, DevelopmentConfig)
