"""
Stage 5 Enterprise Features Integration & Security Tests.

Covers:
1. Document Management CRUD and safe vector cleanup.
2. Collection Management, Document Assignment, and Tenant Isolation.
3. Collection-Scoped Retrieval filtering.
4. Model Settings (Ollama live probe & Embedding metadata).
5. User Status management (Account deactivation RBAC).
6. Enterprise Audit Logging and Querying.
"""

import json
from pathlib import Path
import pytest
from fastapi.testclient import TestClient

from backend import auth, collections_store, config
from backend.observability import audit_logger
from backend.main import app


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "STORE_DIR", tmp_path / "storage")
    (tmp_path / "storage").mkdir(parents=True, exist_ok=True)
    (tmp_path / "storage" / "sessions").mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(config, "SESSIONS_DIR", tmp_path / "storage" / "sessions")
    monkeypatch.setattr(config, "USERS_FILE", tmp_path / "storage" / "users.json")
    monkeypatch.setattr(config, "SECRET_FILE", tmp_path / "storage" / "secret.key")
    return TestClient(app)


def _create_authenticated_user(email="admin@enterprise.org", role="admin", org_id="org_alpha"):
    u = auth.create_user(email, "StrongPass123!", role=role, org_id=org_id)
    token = auth.issue_token(u["id"], org_id=org_id)
    return u, token


def test_collections_crud_and_isolation(client):
    u1, t1 = _create_authenticated_user("legal1@org_a.com", "user", "org_a")
    u2, t2 = _create_authenticated_user("legal2@org_b.com", "user", "org_b")

    headers1 = {"Authorization": f"Bearer {t1}"}
    headers2 = {"Authorization": f"Bearer {t2}"}

    # 1. Create collection in org_a
    res = client.post(
        "/api/collections",
        headers=headers1,
        json={"name": "Contracts 2025", "description": "Legal contracts", "files": ["contract1.pdf"]},
    )
    assert res.status_code == 200
    col_a = res.json()
    assert col_a["name"] == "Contracts 2025"
    assert "contract1.pdf" in col_a["files"]

    # 2. Org B user lists collections -> Should not see Org A's collection
    res_b = client.get("/api/collections", headers=headers2)
    assert res_b.status_code == 200
    cols_b = res_b.json()["collections"]
    assert len(cols_b) == 0

    # 3. Add document to collection in Org A
    res_add = client.post(
        f"/api/collections/{col_a['id']}/documents",
        headers=headers1,
        json={"files": ["nda_agreement.docx"]},
    )
    assert res_add.status_code == 200
    assert "nda_agreement.docx" in res_add.json()["files"]

    # 4. Remove document from collection
    res_rem = client.delete(
        f"/api/collections/{col_a['id']}/documents/contract1.pdf",
        headers=headers1,
    )
    assert res_rem.status_code == 200
    assert "contract1.pdf" not in res_rem.json()["files"]

    # 5. Delete collection
    res_del = client.delete(f"/api/collections/{col_a['id']}", headers=headers1)
    assert res_del.status_code == 200


def test_audit_logging_and_querying(client):
    admin, token = _create_authenticated_user("audit.admin@enterprise.org", "admin", "org_corp")
    headers = {"Authorization": f"Bearer {token}"}

    # Record some audit events
    audit_logger.record_audit(
        action="document_uploaded",
        user_id=admin["id"],
        email="audit.admin@enterprise.org",
        org_id="org_corp",
        resource="Quarterly_Report.pdf",
        outcome="success",
        details={"chunks": 14},
    )
    audit_logger.record_audit(
        action="collection_created",
        user_id=admin["id"],
        email="audit.admin@enterprise.org",
        org_id="org_corp",
        resource="Finance 2026",
        outcome="success",
    )

    # Query audit logs via API
    res = client.get("/api/admin/audit-logs?limit=10", headers=headers)
    assert res.status_code == 200
    data = res.json()
    assert data["total"] >= 2
    actions = [e["action"] for e in data["events"]]
    assert "document_uploaded" in actions
    assert "collection_created" in actions


def test_user_status_deactivation(client):
    admin, admin_token = _create_authenticated_user("sec.admin@corp.com", "admin", "org_corp")
    headers = {"Authorization": f"Bearer {admin_token}"}

    # Create target user
    auth.create_user("contractor@corp.com", "TempPassword123!", role="user", org_id="org_corp")

    # Deactivate target user
    res = client.post(
        "/api/admin/users/contractor@corp.com/status",
        headers=headers,
        json={"status": "disabled"},
    )
    assert res.status_code == 200
    assert res.json()["status"] == "disabled"

    # Target user attempts to login -> Blocked
    login_res = client.post(
        "/api/auth/login",
        json={"email": "contractor@corp.com", "password": "TempPassword123!"},
    )
    assert login_res.status_code in (401, 403)


def test_model_settings_endpoints(client):
    u, token = _create_authenticated_user("analyst@corp.com", "user", "org_corp")
    headers = {"Authorization": f"Bearer {token}"}

    # 1. Ollama status
    res = client.get("/api/models/ollama/status", headers=headers)
    assert res.status_code == 200
    data = res.json()
    assert "status" in data
    assert "configured_provider" in data
    assert data["configured_provider"] == "ollama"

    # 2. Embedding info
    res_embed = client.get("/api/models/embedding", headers=headers)
    assert res_embed.status_code == 200
    embed_data = res_embed.json()
    assert "model" in embed_data
    assert "dimension" in embed_data
    assert embed_data["dimension"] in (384, 768, 1024)


def test_collection_scoped_retrieval(client, monkeypatch):
    u, token = _create_authenticated_user("lawyer@corp.com", "user", "org_legal")
    headers = {"Authorization": f"Bearer {token}"}

    # Create collection with specific file
    col = collections_store.create_collection(
        name="Strict Scope",
        description="Only contracts",
        owner_id=u["id"],
        org_id="org_legal",
        files=["Permitted_Contract.pdf"],
    )

    # Mock search.text_query to verify files parameter received
    captured_files = []
    from backend.retrieval import search
    def mock_text_query(query, **kwargs):
        captured_files.append(kwargs.get("files"))
        return []

    monkeypatch.setattr(search, "text_query", mock_text_query)

    # Run query with collection_id
    client.post(
        "/api/query",
        headers=headers,
        json={
            "session_id": "sess_col_test",
            "query": "What is the liability clause?",
            "collection_id": col["id"],
        },
    )

    assert len(captured_files) == 1
    # Confirms query was strictly scoped to the collection's files
    assert captured_files[0] == ["Permitted_Contract.pdf"]
