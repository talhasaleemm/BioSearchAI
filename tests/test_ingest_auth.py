from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_ingest_requires_auth():
    payload = {
        "title": "Test",
        "source_type": "url",
        "session_id": 1,
        "content": "test content"
    }
    response = client.post("/api/v1/documents/ingest", json=payload)
    # Because it requires auth, it should return 401 Unauthorized
    assert response.status_code == 401
