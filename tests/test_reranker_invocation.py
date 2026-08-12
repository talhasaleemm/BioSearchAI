import pytest
import numpy as np
from unittest.mock import MagicMock

from app.services.retrieval import VectorRetriever
from app.models.chunk import Chunk
from app.models.document import Document
from app.models.search_session import SearchSession
from app.models.user import User
from app.models.session_action import SessionAction
from app.services.faiss_index import faiss_manager

@pytest.mark.asyncio
async def test_retriever_invokes_reranker(monkeypatch):
    retriever = VectorRetriever()
    
    # Mock FAISS to return specific dummy inner-product scores
    async def mock_search(query_vector, top_k):
        # We deliberately return fake descending scores
        return np.array([[0.9, 0.8, 0.7]]), np.array([[101, 102, 103]])
    
    monkeypatch.setattr(faiss_manager, "search", mock_search)
    
    # Mock DB Session
    mock_db = MagicMock()
    
    # Create fake chunks
    doc = Document(id=1, title="Test Doc")
    chunk1 = Chunk(id=101, text="Paris is the capital of France.", document=doc)
    chunk2 = Chunk(id=102, text="London is the capital of the UK.", document=doc)
    chunk3 = Chunk(id=103, text="The Eiffel Tower is in Paris.", document=doc)
    
    # Setup mock query chain
    mock_query = MagicMock()
    mock_filter = MagicMock()
    mock_db.query.return_value = mock_query
    mock_query.filter.return_value = mock_filter
    mock_filter.all.return_value = [chunk1, chunk2, chunk3]
    
    # Call real search_similar_chunks()
    results = await retriever.search_similar_chunks(mock_db, query="What is the capital of France?", top_k=3)
    
    assert len(results) == 3
    
    # Extract the final scores assigned to the chunks
    scores = [score for _, _, score in results]
    
    # If the reranker ran, it overwrote the FAISS distances with CrossEncoder logits/probs.
    # We assert the scores are NO LONGER exactly [0.9, 0.8, 0.7] (or sorted exactly like that without change)
    assert scores != [0.9, 0.8, 0.7], "Scores matched FAISS exactly; reranker was not invoked or did not overwrite scores"
    
    # We can also assert that the real CrossEncoder successfully pushed the best semantic match to the top
    assert "Paris is the capital of France" in results[0][0].text
