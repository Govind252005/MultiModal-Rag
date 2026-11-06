"""
Security Test Suite: Role-Based Access Control and Error Sanitization (SEC-06 & SEC-07).
Validates endpoint authorization boundaries, administrative scoping, and error envelopes.
"""

import pytest
from fastapi.testclient import TestClient
from backend import auth, config
from backend.main import app

client = TestClient(app)


def test_rbac_admin_enforcement(tmp_path, monkeypatch):
    test_user_file = tmp_path / "users_rbac_test.json"
    monkeypatch.setattr(config, "USERS_FILE", test_user_file)

    # 1. Create first user -> Automatically becomes Admin (org_alpha)
    admin_alpha = auth.create_user("admin@alpha.com", "AdminPass123!", org_id="org_alpha")
    assert admin_alpha["role"] == "admin"
    admin_token = auth.issue_token(admin_alpha["id"])

    # 2. Create regular user in org_alpha
    user_alpha = auth.create_user("user@alpha.com", "UserPass123!", org_id="org_alpha")
    assert user_alpha["role"] == "user"
    user_token = auth.issue_token(user_alpha["id"])

    # 3. Create regular user in org_beta
    user_beta = auth.create_user("user@beta.com", "UserBeta123!", org_id="org_beta")
    assert user_beta["role"] == "user"

    # Test A: Unauthenticated request to admin endpoint -> 401
    res = client.get("/api/admin/users")
    assert res.status_code == 401
    err = res.json()["error"]
    assert err["code"] == "UNAUTHORIZED"

    # Test B: Regular user request to admin endpoint -> 403
    res = client.get("/api/admin/users", headers={"Authorization": f"Bearer {user_token}"})
    assert res.status_code == 403
    err = res.json()["error"]
    assert err["code"] == "FORBIDDEN"

    # Test C: Admin gets scoped user list -> Only sees org_alpha
    res = client.get("/api/admin/users", headers={"Authorization": f"Bearer {admin_token}"})
    assert res.status_code == 200
    listed_emails = [u["email"] for u in res.json()["users"]]
    assert "admin@alpha.com" in listed_emails
    assert "user@alpha.com" in listed_emails
    assert "user@beta.com" not in listed_emails

    # Test D: Admin attempts to alter role of user in different org -> 403
    res = client.post(
        "/api/admin/users/user@beta.com/role",
        json={"role": "admin"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert res.status_code == 403

    # Test E: Admin alters role of user in same org -> 200
    res = client.post(
        "/api/admin/users/user@alpha.com/role",
        json={"role": "viewer"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert res.status_code == 200
    assert res.json()["role"] == "viewer"

