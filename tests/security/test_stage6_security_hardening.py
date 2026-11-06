"""
Stage 6: Enterprise Security Hardening & Vulnerability Verification Test Suite.
Validates:
1. Disabled user account blocking (login rejection & active token invalidation).
2. Role-Based Access Control (RBAC): Standard users strictly blocked from Admin routes.
3. Cross-Tenant Isolation: Prevention of cross-tenant document download, deletion, and collection manipulation.
4. Path Traversal & Injection Defense: Prevention of traversal sequences in document endpoints.
5. File Magic-Byte Validation: Enforcement of authentic binary signatures on upload.
6. Audit Logging Integrity: Verification of non-repudiation audit trails for sensitive operations.
"""

import io
import pytest
from pathlib import Path
from fastapi.testclient import TestClient

from backend.main import app
from backend import auth, config, sessions, collections_store
from backend.observability import audit_logger
from backend.retrieval import vector_store

client = TestClient(app)


@pytest.fixture
def enterprise_security_env(tmp_path, monkeypatch):
    """Sets up an isolated multi-tenant enterprise test environment."""
    user_file = tmp_path / "users_stage6.json"
    sessions_dir = tmp_path / "sessions_stage6"
    collections_file = tmp_path / "collections_stage6.json"
    audit_file = tmp_path / "audit_stage6.jsonl"
    sessions_dir.mkdir(parents=True, exist_ok=True)

    monkeypatch.setattr(config, "USERS_FILE", user_file)
    monkeypatch.setattr(config, "SESSIONS_DIR", sessions_dir)
    monkeypatch.setattr(config, "DATA_DIR", tmp_path)
    monkeypatch.setattr(collections_store, "_col_path", lambda: collections_file)
    monkeypatch.setattr(audit_logger, "_audit_file", lambda: audit_file)

    # 1. Admin in tenant alpha
    admin_alpha = auth.create_user("admin@alpha.com", "AdminPass123!", role="admin", org_id="org_alpha")
    admin_token = auth.issue_token(admin_alpha["id"], org_id="org_alpha")

    # 2. Standard user in tenant alpha
    user_alpha = auth.create_user("alice@alpha.com", "AlicePass123!", role="user", org_id="org_alpha")
    user_alpha_token = auth.issue_token(user_alpha["id"], org_id="org_alpha")

    # 3. Standard user in tenant beta
    user_beta = auth.create_user("bob@beta.com", "BobPass123!", role="user", org_id="org_beta")
    user_beta_token = auth.issue_token(user_beta["id"], org_id="org_beta")

    # 4. User in tenant alpha that will be disabled
    user_disabled = auth.create_user("disabled@alpha.com", "DisabledPass123!", role="user", org_id="org_alpha")
    disabled_token = auth.issue_token(user_disabled["id"], org_id="org_alpha")
    auth.set_status("disabled@alpha.com", "disabled", org_id="org_alpha")

    # Setup an Alpha session and document
    sess_alpha = "sess_alpha_101"
    sessions.ensure_exists(sess_alpha, user_alpha["id"], org_id="org_alpha")
    sess_dir = tmp_path / sess_alpha
    sess_dir.mkdir(parents=True, exist_ok=True)
    doc_path = sess_dir / "confidential_alpha_report.txt"
    doc_path.write_text("CONFIDENTIAL ALPHA M&A STRATEGY 2026", encoding="utf-8")

    # Index doc in vector store and register in session
    vector_store.add_text_chunks(
        ids=["chunk_alpha_sec_6"],
        embeddings=[[0.01] * 384],
        documents=["CONFIDENTIAL ALPHA M&A STRATEGY 2026"],
        metadatas=[{
            "file": "confidential_alpha_report.txt",
            "session_id": sess_alpha,
            "user_id": user_alpha["id"],
            "org_id": "org_alpha",
            "modality": "document",
        }],
    )
    sessions.set_files(sess_alpha, ["confidential_alpha_report.txt"])

    # Create Alpha Collection
    col_alpha = collections_store.create_collection(
        name="Alpha Strategic Vault",
        owner_id=user_alpha["id"],
        org_id="org_alpha",
        files=["confidential_alpha_report.txt"],
    )

    return {
        "admin_alpha": admin_alpha,
        "admin_token": admin_token,
        "user_alpha": user_alpha,
        "user_alpha_token": user_alpha_token,
        "user_beta": user_beta,
        "user_beta_token": user_beta_token,
        "user_disabled": user_disabled,
        "disabled_token": disabled_token,
        "sess_alpha": sess_alpha,
        "col_alpha": col_alpha,
        "file_alpha": "confidential_alpha_report.txt",
    }


def test_disabled_user_login_rejected(enterprise_security_env):
    """Disabled user cannot obtain a new JWT token via login endpoint."""
    resp = client.post(
        "/api/auth/login",
        json={"email": "disabled@alpha.com", "password": "DisabledPass123!"},
    )
    assert resp.status_code == 403
    assert "account is disabled" in str(resp.json()).lower()


def test_disabled_user_token_rejected_at_protected_endpoints(enterprise_security_env):
    """Even if a disabled user holds a previously-issued valid token, get_user rejects with 403."""
    token = enterprise_security_env["disabled_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Protected endpoints must reject with 403
    r_docs = client.get("/api/documents", headers=headers)
    assert r_docs.status_code == 403
    assert "account is disabled" in str(r_docs.json()).lower()

    r_cols = client.get("/api/collections", headers=headers)
    assert r_cols.status_code == 403


def test_standard_user_cannot_access_admin_endpoints(enterprise_security_env):
    """Standard non-admin users must be strictly blocked with 403 from admin console endpoints."""
    token = enterprise_security_env["user_alpha_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Admin user list
    r1 = client.get("/api/admin/users", headers=headers)
    assert r1.status_code == 403

    # Admin audit logs
    r2 = client.get("/api/admin/audit-logs", headers=headers)
    assert r2.status_code == 403

    # Admin role modification
    r3 = client.post(
        "/api/admin/users/alice@alpha.com/role",
        json={"role": "admin"},
        headers=headers,
    )
    assert r3.status_code == 403


def test_cross_tenant_document_download_blocked(enterprise_security_env):
    """User in org_beta cannot download documents belonging to org_alpha."""
    beta_token = enterprise_security_env["user_beta_token"]
    sess_alpha = enterprise_security_env["sess_alpha"]
    fname = enterprise_security_env["file_alpha"]

    resp = client.get(
        f"/api/documents/{sess_alpha}/{fname}/download",
        headers={"Authorization": f"Bearer {beta_token}"},
    )
    # Must be 403 or 404 forbidden/not found
    assert resp.status_code in (403, 404)


def test_cross_tenant_document_deletion_blocked(enterprise_security_env):
    """User in org_beta cannot delete documents belonging to org_alpha."""
    beta_token = enterprise_security_env["user_beta_token"]
    fname = enterprise_security_env["file_alpha"]

    resp = client.delete(
        f"/api/documents/{fname}",
        headers={"Authorization": f"Bearer {beta_token}"},
    )
    assert resp.status_code == 404
    assert "not found or access denied" in str(resp.json()).lower()


def test_cross_tenant_collection_access_blocked(enterprise_security_env):
    """User in org_beta cannot access, mutate, or delete org_alpha's collections."""
    beta_token = enterprise_security_env["user_beta_token"]
    col_id = enterprise_security_env["col_alpha"]["id"]
    headers = {"Authorization": f"Bearer {beta_token}"}

    # Get collection
    r1 = client.get(f"/api/collections/{col_id}", headers=headers)
    assert r1.status_code == 404

    # Update collection
    r2 = client.patch(f"/api/collections/{col_id}", json={"name": "Hacked"}, headers=headers)
    assert r2.status_code == 404

    # Delete collection
    r3 = client.delete(f"/api/collections/{col_id}", headers=headers)
    assert r3.status_code == 404


def test_path_traversal_on_download_and_content_rejected(enterprise_security_env):
    """Directory traversal payloads (../, %2e%2e) are safely blocked."""
    token = enterprise_security_env["user_alpha_token"]
    sess = enterprise_security_env["sess_alpha"]
    headers = {"Authorization": f"Bearer {token}"}

    # Attempt directory traversal in download
    r1 = client.get(f"/api/documents/{sess}/../../etc/passwd/download", headers=headers)
    assert r1.status_code in (400, 404)

    # Attempt traversal in content
    r2 = client.get(f"/api/documents/{sess}/..%2f..%2fconfig.py/content", headers=headers)
    assert r2.status_code in (400, 404)


def test_file_signature_magic_byte_validation_rejects_spoofed_file(enterprise_security_env):
    """Uploading an executable disguised as a PDF must be rejected by magic byte inspection."""
    token = enterprise_security_env["user_alpha_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Fake PDF file containing plain Windows PE executable signature or random text
    fake_pdf = io.BytesIO(b"MZ\x90\x00\x03\x00\x00\x00This is an executable disguised as pdf")
    fake_pdf.name = "trojan_disguised.pdf"

    resp = client.post(
        "/api/documents/upload",
        files=[("files", (fake_pdf.name, fake_pdf, "application/pdf"))],
        headers=headers,
    )
    assert resp.status_code == 400
    assert "magic-byte check failed" in str(resp.json()).lower()


def test_audit_logging_integrity(enterprise_security_env):
    """Admin operations record verifiable audit log entries with ISO timestamp, user email, and action."""
    admin_token = enterprise_security_env["admin_token"]
    headers = {"Authorization": f"Bearer {admin_token}"}

    # Trigger admin action: toggle user status
    r_act = client.post(
        "/api/admin/users/alice@alpha.com/status",
        json={"status": "disabled"},
        headers=headers,
    )
    assert r_act.status_code == 200

    # Query audit logs as admin
    r_logs = client.get("/api/admin/audit-logs", headers=headers)
    assert r_logs.status_code == 200
    logs = r_logs.json().get("logs", [])
    assert len(logs) > 0

    actions = [l["action"] for l in logs]
    assert "user_status_changed" in actions
    matching = [l for l in logs if l["action"] == "user_status_changed"]
    assert matching[0]["email"] == "admin@alpha.com"
    assert matching[0]["outcome"] == "success"
