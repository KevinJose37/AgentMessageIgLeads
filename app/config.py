from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # --- App ---
    APP_NAME: str = "IG Message Variation Service"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False

    # --- Authentication ---
    API_KEY: str = "change-me-in-production"

    # --- Ollama ---
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    OLLAMA_MODEL: str = "mistral"
    OLLAMA_TIMEOUT: int = 600  # 10 min — CPU inference is slow

    # --- Generation ---
    DEFAULT_NUM_VARIATIONS: int = 20
    MAX_VARIATIONS_PER_REQUEST: int = 100
    BATCH_SIZE: int = 10  # Variations per single inference call
    TEMPERATURE: float = 0.8

    # --- Cache ---
    CACHE_ENABLED: bool = True
    CACHE_DB_PATH: str = "data/cache.db"
    CACHE_TTL_HOURS: int = 168  # 7 days

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


@lru_cache()
def get_settings() -> Settings:
    return Settings()
