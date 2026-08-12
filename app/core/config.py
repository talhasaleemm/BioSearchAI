from __future__ import annotations

import os
from functools import lru_cache
from typing import Optional

from pydantic_settings import BaseSettings


# HuggingFace Hub model IDs — used as fallbacks when local paths don't exist.
_HF_EMBEDDING_MODEL = "pritamdeka/S-PubMedBert-MS-MARCO"
_HF_RERANKER_MODEL = "cross-encoder/ms-marco-MiniLM-L-6-v2"
# NER model is custom fine-tuned (BioBERT + BC5CDR) — no public Hub ID exists.
# When the local checkpoint is absent, NER gracefully degrades to no-op.


def _resolve_path(local_path: Optional[str], hub_fallback: Optional[str]) -> Optional[str]:
    """Return *local_path* if it exists on disk, otherwise *hub_fallback*.

    This lets the same config work both in docker-compose (bind-mounted
    .model_cache) and on Railway / bare-metal where models must be
    downloaded from HuggingFace Hub on first use.
    """
    if local_path and os.path.isdir(local_path):
        return local_path
        
    # Local Windows fallback: if running tests outside Docker, `/app/.model_cache` 
    # won't exist. Strip `/app/` to check relative to CWD.
    if local_path and local_path.startswith("/app/"):
        rel_path = local_path[5:]
        if os.path.isdir(rel_path):
            return rel_path
            
    return hub_fallback



class Settings(BaseSettings):
    DATABASE_URL: str = "postgresql://postgres:postgres@localhost:5432/biosearchai"
    SECRET_KEY: str = "change-me-in-production-use-a-strong-random-key"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24

    CORS_ALLOWED_ORIGINS: str = "http://localhost:3000"

    OPENAI_API_KEY: Optional[str] = "ollama"
    OPENAI_API_BASE: str = "http://host.docker.internal:11434/v1"
    HF_HUB_OFFLINE: int = 0
    DISABLE_BACKGROUND_TASKS: bool = False
    OPENAI_MODEL: str = "llama3.2:1b"

    # Raw local paths — kept as the primary setting so docker-compose dev
    # workflow is unchanged.  _resolve_path() checks existence at runtime.
    ENABLE_RERANKER: bool = True

    EMBEDDING_MODEL_PATH: str = "/app/.model_cache/pritamdeka-S-PubMedBert-MS-MARCO"
    # Local path for cross-encoder reranker. Set to None to disable reranking (graceful degradation).
    # Populate .model_cache/cross-encoder-ms-marco-MiniLM-L-6-v2/ on the host, then this
    # default resolves via the bind-mount to /app/.model_cache/... inside the container.
    RERANKER_MODEL_PATH: Optional[str] = "/app/.model_cache/cross-encoder-ms-marco-MiniLM-L-6-v2"
    NER_MODEL_PATH: Optional[str] = "/app/.model_cache/biobert-ner-bc5cdr"

    model_config = {"env_file": ".env", "extra": "ignore"}

    # --- Resolved model identifiers (local path OR Hub ID) ----------------

    @property
    def resolved_embedding_model(self) -> str:
        return _resolve_path(self.EMBEDDING_MODEL_PATH, _HF_EMBEDDING_MODEL) or _HF_EMBEDDING_MODEL

    @property
    def resolved_reranker_model(self) -> Optional[str]:
        return _resolve_path(self.RERANKER_MODEL_PATH, _HF_RERANKER_MODEL)

    @property
    def resolved_ner_model(self) -> Optional[str]:
        # Custom fine-tuned model — no Hub fallback exists.
        # Returns the local path if present, None otherwise (NER degrades).
        return _resolve_path(self.NER_MODEL_PATH, None)


@lru_cache()
def get_settings() -> Settings:
    return Settings()
