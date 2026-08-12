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
        self._rlock = threading.RLock()
        # Use exact inner product search (requires normalized vectors)
        base_index = faiss.IndexFlatIP(self.dim)
        # Wrap in IndexIDMap to track chunk.id
        self.index = faiss.IndexIDMap(base_index)

    async def add_with_ids(self, embeddings: np.ndarray, ids: np.ndarray) -> None:
        """Add embeddings with their corresponding chunk IDs to the index safely (async path)."""
        if embeddings.shape[0] == 0:
            return
            
        def _add():
            with self._rlock:
                self.index.add_with_ids(embeddings, ids)
                
        # Dispatch both lock acquisition and CPU-bound FAISS add to the same thread
        await asyncio.to_thread(_add)
        logger.info(f"Added {embeddings.shape[0]} vectors to FAISS index. Total: {self.index.ntotal}")

    def add_with_ids_sync(self, embeddings: np.ndarray, ids: np.ndarray) -> None:
        """Add embeddings synchronously (for Celery workers, CLI scripts, and sync test helpers)."""
        if embeddings.shape[0] == 0:
            return
        with self._rlock:
            self.index.add_with_ids(embeddings, ids)
            logger.info(f"[sync] Added {embeddings.shape[0]} vectors to FAISS index. Total: {self.index.ntotal}")

    async def search(self, query_vector: np.ndarray, top_k: int) -> Tuple[np.ndarray, np.ndarray]:
        """Search for similar vectors safely."""
        if self.index.ntotal == 0:
            return np.array([[]]), np.array([[]])
            
        def _search():
            with self._rlock:
                return self.index.search(np.array([query_vector], dtype=np.float32), top_k)
                
        # Dispatch both lock acquisition and CPU-bound FAISS search to the same thread
        distances, indices = await asyncio.to_thread(_search)
        return distances, indices

faiss_manager = FAISSIndexManager()
