import pytest
from fastapi.testclient import TestClient
from pathlib import Path
from backend.main import app
from backend import auth, sessions, config

client = TestClient(app)

@pytest.fixture
def auth_setup(tmp_path, monkeypatch):
    test_user_file = tmp_path / "users_test.json"
    sessions_dir = tmp_path / "sessions"
    sessions_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(config, "USERS_FILE", test_user_file)
    monkeypatch.setattr(config, "SESSIONS_DIR", sessions_dir)
    monkeypatch.setattr(config, "DATA_DIR", tmp_path)
    
    # Register user 1 in org_a
    u1 = auth.create_user("alice@org-a.com", "Password123!", org_id="org_a")
    t1 = auth.issue_token(u1["id"], org_id="org_a")
    
    # Register user 2 in org_b
    u2 = auth.create_user("bob@org-b.com", "Password123!", org_id="org_b")
    t2 = auth.issue_token(u2["id"], org_id="org_b")
    
    # Create session for Alice
    s1 = "session_alice_doc"
    sessions.ensure_exists(s1, u1["id"], org_id="org_a")
    
    # Create sample text file in Alice's session directory
    s1_dir = tmp_path / s1
    s1_dir.mkdir(parents=True, exist_ok=True)
    sample_file = s1_dir / "sample_contract.txt"
    sample_file.write_text("Clause 1: Confidentiality obligation.\nClause 2: Governing Law is California.", encoding="utf-8")
    
    return {
        "user1": u1, "token1": t1, "session1": s1,
        "user2": u2, "token2": t2,
        "file1": "sample_contract.txt",
    }

def test_document_content_unauthorized(auth_setup):
    s1 = auth_setup["session1"]
    fname = auth_setup["file1"]
    # No auth header -> 401
    resp = client.get(f"/api/documents/{s1}/{fname}/content")
    assert resp.status_code == 401

def test_document_content_cross_tenant_forbidden(auth_setup):
    s1 = auth_setup["session1"]
    fname = auth_setup["file1"]
    t2 = auth_setup["token2"] # Bob from org_b
    
    # Bob trying to view Alice's session document -> 404 (session isolation)
    resp = client.get(
        f"/api/documents/{s1}/{fname}/content",
        headers={"Authorization": f"Bearer {t2}"}
    )
    assert resp.status_code == 404

def test_document_content_path_traversal_blocked(auth_setup):
    s1 = auth_setup["session1"]
    t1 = auth_setup["token1"]
    
    # Traversal attack
    resp = client.get(
        f"/api/documents/{s1}/..%2f..%2fsecret.key/content",
        headers={"Authorization": f"Bearer {t1}"}
    )
    assert resp.status_code in (400, 404)

def test_document_content_authorized_success(auth_setup):
    s1 = auth_setup["session1"]
    fname = auth_setup["file1"]
    t1 = auth_setup["token1"]
    
    resp = client.get(
        f"/api/documents/{s1}/{fname}/content",
        headers={"Authorization": f"Bearer {t1}"}
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["filename"] == fname
    assert data["modality"] == "text"
    assert "Clause 1: Confidentiality" in data["content"]
