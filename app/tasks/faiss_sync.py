import asyncio
import logging
from sqlalchemy.orm import Session
import numpy as np

from app.models import SessionLocal
from app.models.chunk import Chunk
from app.services.faiss_index import faiss_manager

logger = logging.getLogger(__name__)

async def periodic_faiss_sync(interval_seconds: int = 30):
    """Background task to poll for new chunks and add them to FAISS."""
    last_sync_id = 0
    
    while True:
        try:
            db = SessionLocal()
            try:
                # Fetch new chunks that have embeddings
                new_chunks = db.query(Chunk).filter(
                    Chunk.id > last_sync_id,
                    Chunk.embedding.is_not(None)
                ).order_by(Chunk.id.asc()).all()
                
                if new_chunks:
                    embeddings = np.array([chunk.embedding for chunk in new_chunks], dtype=np.float32)
                    ids = np.array([chunk.id for chunk in new_chunks], dtype=np.int64)
                    
                    await faiss_manager.add_with_ids(embeddings, ids)
                    
                    last_sync_id = new_chunks[-1].id
                    logger.info(f"FAISS sync complete. Synced up to chunk ID {last_sync_id}")
            finally:
                db.close()
        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.error(f"Error in FAISS sync task: {e}")
            
        await asyncio.sleep(interval_seconds)
