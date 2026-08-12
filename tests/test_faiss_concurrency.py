import asyncio
import concurrent.futures
import numpy as np
import pytest
from app.services.faiss_index import faiss_manager

@pytest.mark.asyncio
async def test_faiss_dual_lock_race():
    """
    Spawns multiple async tasks and sync threads simultaneously adding to the FAISS index.
    Under the old dual-lock design (where async and sync paths held separate locks),
    FAISS would receive concurrent writes, leading to dropped writes or segfaults.
    With a single RLock, ntotal should be perfectly deterministic.
    """
    # Reset index for clean test
    faiss_manager._init_index()
    
    num_writers = 100
    vectors_per_writer = 10
    
    dim = 768
    
    async def async_writer(start_id):
        embeddings = np.random.rand(vectors_per_writer, dim).astype("float32")
        ids = np.arange(start_id, start_id + vectors_per_writer)
        # Yield to event loop to increase overlap chance
        await asyncio.sleep(0.01)
        await faiss_manager.add_with_ids(embeddings, ids)
        
    def sync_writer(start_id):
        embeddings = np.random.rand(vectors_per_writer, dim).astype("float32")
        ids = np.arange(start_id, start_id + vectors_per_writer)
        import time
        time.sleep(0.01)
        faiss_manager.add_with_ids_sync(embeddings, ids)

    tasks = []
    
    loop = asyncio.get_running_loop()
    with concurrent.futures.ThreadPoolExecutor(max_workers=num_writers) as pool:
        for i in range(num_writers):
            tasks.append(asyncio.create_task(async_writer(i * 2 * vectors_per_writer)))
            tasks.append(loop.run_in_executor(
                pool, sync_writer, (i * 2 + 1) * vectors_per_writer
            ))
            
        await asyncio.gather(*tasks)

    expected_total = num_writers * 2 * vectors_per_writer
    assert faiss_manager.index.ntotal == expected_total, f"Expected {expected_total}, got {faiss_manager.index.ntotal}"
