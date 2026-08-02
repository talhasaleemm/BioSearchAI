from __future__ import annotations

from functools import lru_cache
from typing import Optional

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    DATABASE_URL: str = "postgresql://postgres:postgres@localhost:5432/biosearchai"
    SECRET_KEY: str = "change-me-in-production-use-a-strong-random-key"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24

    OPENAI_API_KEY: Optional[str] = None
    OPENAI_API_BASE: str = "https://api.openai.com/v1"
    OPENAI_MODEL: str = "gpt-4o-mini"

    EMBEDDING_MODEL_PATH: str = "/app/.model_cache/pritamdeka-S-PubMedBert-MS-MARCO"
    # Local path for cross-encoder reranker. Set to None to disable reranking (graceful degradation).
    # Populate .model_cache/cross-encoder-ms-marco-MiniLM-L-6-v2/ on the host, then this
    # default resolves via the bind-mount to /app/.model_cache/... inside the container.
    RERANKER_MODEL_PATH: Optional[str] = "/app/.model_cache/cross-encoder-ms-marco-MiniLM-L-6-v2"

    model_config = {"env_file": ".env", "extra": "ignore"}


@lru_cache()
def get_settings() -> Settings:
    return Settings()
