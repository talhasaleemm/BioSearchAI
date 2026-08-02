import asyncio
import logging
import threading
from typing import List, Tuple

import faiss
import numpy as np

logger = logging.getLogger(__name__)

class FAISSIndexManager:
    """Thread-safe and async-safe wrapper for FAISS index operations."""
    
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(FAISSIndexManager, cls).__new__(cls)
            cls._instance._init_index()
        return cls._instance
        
    def _init_index(self):
        self.dim = 768
        self.last_sync_timestamp = None
        self._lock = asyncio.Lock()
        self._thread_lock = threading.Lock()  # for sync callers (Celery, tests)
        # Use exact inner product search (requires normalized vectors)
        base_index = faiss.IndexFlatIP(self.dim)
        # Wrap in IndexIDMap to track chunk.id
        self.index = faiss.IndexIDMap(base_index)

    async def add_with_ids(self, embeddings: np.ndarray, ids: np.ndarray) -> None:
        """Add embeddings with their corresponding chunk IDs to the index safely (async path)."""
        if embeddings.shape[0] == 0:
            return
            
        async with self._lock:
            # Dispatch CPU-bound FAISS add operation to executor
            await asyncio.to_thread(self.index.add_with_ids, embeddings, ids)
            logger.info(f"Added {embeddings.shape[0]} vectors to FAISS index. Total: {self.index.ntotal}")

    def add_with_ids_sync(self, embeddings: np.ndarray, ids: np.ndarray) -> None:
        """Add embeddings synchronously (for Celery workers, CLI scripts, and sync test helpers).

        Uses a threading.Lock separate from the asyncio.Lock so this is safe to call from any
        thread without touching the event loop.
        """
        if embeddings.shape[0] == 0:
            return
        with self._thread_lock:
            self.index.add_with_ids(embeddings, ids)
            logger.info(f"[sync] Added {embeddings.shape[0]} vectors to FAISS index. Total: {self.index.ntotal}")

    async def search(self, query_vector: np.ndarray, top_k: int) -> Tuple[np.ndarray, np.ndarray]:
        """Search for similar vectors safely."""
        if self.index.ntotal == 0:
            return np.array([[]]), np.array([[]])
            
        async with self._lock:
            # Dispatch CPU-bound FAISS search operation to executor
            distances, indices = await asyncio.to_thread(
                self.index.search, np.array([query_vector], dtype=np.float32), top_k
            )
            return distances, indices

faiss_manager = FAISSIndexManager()
