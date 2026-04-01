from pydantic_settings import BaseSettings
from functools import lru_cache
from typing import Optional


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # --- App ---
    APP_NAME: str = "IG Message Variation Service"
    APP_VERSION: str = "1.1.0"
    DEBUG: bool = False

    # --- Authentication ---
    API_KEY: str = "change-me-in-production"

    # --- Groq (Primary) ---
    GROQ_API_KEY: str = ""
    GROQ_MODEL: str = "llama-3.3-70b-versatile"
    GROQ_TIMEOUT: int = 60

    # --- Google Gemini (Fallback — add key to enable) ---
    GEMINI_API_KEY: str = ""
    GEMINI_MODEL: str = "gemini-2.0-flash"
    GEMINI_TIMEOUT: int = 60

    # --- OpenAI (Fallback — add key to enable) ---
    OPENAI_API_KEY: str = ""
    OPENAI_MODEL: str = "gpt-4o-mini"
    OPENAI_TIMEOUT: int = 60

    # --- Generation ---
    DEFAULT_NUM_VARIATIONS: int = 20
    MAX_VARIATIONS_PER_REQUEST: int = 100
    BATCH_SIZE: int = 10
    TEMPERATURE: float = 0.7

    # --- Cache ---
    CACHE_ENABLED: bool = True
    CACHE_DB_PATH: str = "data/cache.db"
    CACHE_TTL_HOURS: int = 168  # 7 days

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


@lru_cache()
def get_settings() -> Settings:
    return Settings()
