"""
Phase 8 Production Monitoring, Health Probes & Incident Response Tests.
Verifies:
1. /health/live liveness probe for orchestrators (k8s / systemd).
2. /health/ready readiness probe reflecting storage and local LLM availability.
3. /health/dependencies deep inspection endpoint reporting SQLite FTS5, ChromaDB,
   Ollama, disk space, and circuit breakers.
4. /metrics Prometheus-scrapeable endpoint.
5. Simulated dependency failure graceful degradation.
"""

from unittest.mock import patch
import pytest
from fastapi.testclient import TestClient
from backend.main import app


@pytest.fixture
def client():
    return TestClient(app)


def test_health_liveness_probe(client: TestClient):
    res = client.get("/health/live")
    assert res.status_code == 200
    assert res.json() == {"status": "alive"}


def test_health_readiness_probe(client: TestClient):
    res = client.get("/health/ready")
    assert res.status_code == 200
    body = res.json()
    assert "status" in body
    assert "storage" in body
    assert "ollama" in body


def test_health_dependencies_deep_check(client: TestClient):
    res = client.get("/health/dependencies")
    assert res.status_code == 200
    body = res.json()
    assert body["status"] == "healthy"
    assert body["storage"] == "ok"
    assert "sqlite_fts5" in body
    assert "disk" in body
    assert "total_bytes" in body["disk"]
    assert "free_gb" in body["disk"]
    assert "circuit_breakers" in body
    assert "ollama" in body


def test_prometheus_metrics_exposition(client: TestClient):
    res = client.get("/metrics")
    assert res.status_code == 200
    assert "text/plain" in res.headers.get("content-type", "")
    assert "http_requests_total" in res.text or "process_" in res.text or "# HELP" in res.text


def test_health_ready_degrades_when_ollama_unavailable(client: TestClient):
    with patch("backend.main.llm_client.is_available", return_value=False):
        res = client.get("/health/ready")
        assert res.status_code == 200
        body = res.json()
        assert body["status"] == "not_ready"
        assert body["ollama"] == "unavailable"
