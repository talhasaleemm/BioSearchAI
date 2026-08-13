import pytest
from unittest.mock import AsyncMock, patch
from fastapi.testclient import TestClient
import app.services.pubmed
from app.services.pubmed import PubMedService, pubmed_service
from app.main import app

client = TestClient(app)

@pytest.fixture
def mock_pubmed():
    with patch("app.services.pubmed.httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client_cls.return_value.__aenter__.return_value = mock_client
        yield mock_client

@pytest.mark.asyncio
async def test_pubmed_service_search_mocked(mock_pubmed):
    from unittest.mock import MagicMock
    mock_response = MagicMock()
    mock_response.json.return_value = {"esearchresult": {"idlist": ["12345", "67890"]}}
    mock_pubmed.get.return_value = mock_response

    pmids = await pubmed_service.search_pubmed("test cancer", max_results=2)
    assert pmids == ["12345", "67890"]

@pytest.mark.asyncio
async def test_pubmed_service_fetch_mocked(mock_pubmed):
    xml_content = """
    <PubmedArticleSet>
        <PubmedArticle>
            <MedlineCitation>
                <PMID>12345</PMID>
                <Article>
                    <ArticleTitle>Test Article</ArticleTitle>
                    <Abstract>
                        <AbstractText Label="BACKGROUND">Background info.</AbstractText>
                        <AbstractText Label="METHODS">Method info.</AbstractText>
                    </Abstract>
                    <Journal>
                        <JournalIssue>
                            <PubDate>
                                <Year>2023</Year>
                            </PubDate>
                        </JournalIssue>
                    </Journal>
                </Article>
            </MedlineCitation>
        </PubmedArticle>
    </PubmedArticleSet>
    """
    from unittest.mock import MagicMock
    mock_response = MagicMock()
    mock_response.text = xml_content
    mock_pubmed.get.return_value = mock_response

    results = await pubmed_service.fetch_pubmed_abstracts(["12345"])
    assert len(results) == 1
    assert results[0]["pmid"] == "12345"
    assert results[0]["title"] == "Test Article"
    assert "BACKGROUND: Background info." in results[0]["abstract"]
    assert "METHODS: Method info." in results[0]["abstract"]
    assert results[0]["year"] == "2023"

def test_api_pubmed_search(mock_pubmed):
    from app.core.deps import get_current_user
    from app.models.user import User
    
    app.dependency_overrides[get_current_user] = lambda: User(id=1, email="test@example.com")
    
    with patch("app.api.v1.endpoints.documents.pubmed_service.search_pubmed", new_callable=AsyncMock) as mock_search:
        with patch("app.api.v1.endpoints.documents.pubmed_service.fetch_pubmed_abstracts", new_callable=AsyncMock) as mock_fetch:
            mock_search.return_value = ["123"]
            mock_fetch.return_value = [{"pmid": "123", "title": "Test", "abstract": "Test abstract", "year": "2022"}]
            
            response = client.post("/api/v1/documents/pubmed-search", json={"query": "test", "max_results": 1})
            assert response.status_code == 200
            data = response.json()
            assert len(data["results"]) == 1
            assert data["results"][0]["pmid"] == "123"
            
    app.dependency_overrides.clear()

def test_api_pubmed_ingest_empty_abstract(mock_pubmed):
    from app.core.deps import get_current_user
    from app.core.db import get_db
    from app.models.user import User
    from app.models.search_session import SearchSession
    
    class MockSession:
        def get(self, model, id):
            return SearchSession(id=1, user_id=1, session_name="Test")
            
    app.dependency_overrides[get_current_user] = lambda: User(id=1, email="test@example.com")
    app.dependency_overrides[get_db] = lambda: MockSession()
    
    with patch("app.api.v1.endpoints.documents.pubmed_service.fetch_pubmed_abstracts", new_callable=AsyncMock) as mock_fetch:
        mock_fetch.return_value = [{"pmid": "123", "title": "Test", "abstract": "", "year": "2022"}]
        
        response = client.post("/api/v1/documents/pubmed-ingest", json={"pmid": "123", "session_id": 1})
        assert response.status_code == 400
        assert "No abstract available" in response.json()["detail"]
        
    app.dependency_overrides.clear()

if __name__ == "__main__":
    import asyncio
    print("Running live PubMed query for 'BRCA1 breast cancer' to verify real API works...")
    async def run_live():
        service = PubMedService()
        pmids = await service.search_pubmed("BRCA1 breast cancer", max_results=2)
        print(f"Found PMIDs: {pmids}")
        if pmids:
            results = await service.fetch_pubmed_abstracts(pmids)
            for r in results:
                print(f"\\nPMID: {r['pmid']}")
                print(f"Title: {r['title']}")
                print(f"Year: {r['year']}")
                print(f"Abstract preview: {r['abstract'][:150]}...")
    asyncio.run(run_live())
