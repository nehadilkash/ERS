import pytest
from fastapi.testclient import TestClient
from src.main import app
from src.vector.vectorstore import SecurityLogVectorStore

client = TestClient(app)

@pytest.fixture(scope="module")
def setup_vector_store():
    """Initialize a clean vector store for testing."""
    test_store = SecurityLogVectorStore(persist_directory="./test_chroma_db")
    yield test_store


def test_ingest_multiline_log(setup_vector_store):
    """Test ingestion of logs with complex multi-line stack traces."""
    payload = {
        "logs": [
            {
                "timestamp": "2026-10-31T14:30:00Z",
                "service_name": "auth-service",
                "severity": "ERROR",
                "trace_id": "tr-998877",
                "message": (
                    "DatabaseConnectionTimeoutError: Primary pool exhausted.\n"
                    "  at com.auth.db.Pool.getConnection(Pool.java:124)\n"
                    "  at com.auth.service.LoginService.authenticate(LoginService.java:45)\n"
                    "  at com.auth.controller.AuthController.login(AuthController.java:30)"
                )
            },
            {
                "timestamp": "2026-10-31T14:35:00Z",
                "service_name": "payment-gateway",
                "severity": "CRITICAL",
                "trace_id": "tr-112233",
                "message": "Unauthorized API key usage detected from remote host 192.168.1.50"
            }
        ]
    }

    response = client.post("/ingest", json=payload)
    assert response.status_code == 200
    assert response.json()["status"] == "success"
    assert response.json()["processed_logs"] == 2


def test_query_with_filters_and_smart_extraction():
    """Test semantic query with metadata filters and anti-hallucination prompt."""
    query_payload = {
        "query": "Show me database pool exhaustion errors in auth-service",
        "service_name": "auth-service",
        "severity": "ERROR"
    }

    response = client.post("/query", json=query_payload)
    assert response.status_code == 200
    res_data = response.json()

    assert "query" in res_data
    assert "response" in res_data
    assert res_data["response"] != "No matching logs were found in the database for your query criteria."


def test_anti_hallucination_guardrail():
    """Verify that queries for unrecorded vulnerabilities trigger the guardrail response."""
    query_payload = {
        "query": "Did any SQL injection occur on the user accounts table?"
    }

    response = client.post("/query", json=query_payload)
    assert response.status_code == 200
    res_data = response.json()
    
    # Assert that the guardrail or negative response is returned instead of fabricated content
    assert "cannot verify" in res_data["response"].lower() or "no matching logs" in res_data["response"].lower()