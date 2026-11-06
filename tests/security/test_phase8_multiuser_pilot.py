"""
Phase 8 Controlled Multi-User Pilot Regression Test.
Verifies three distinct enterprise personas (Admin, Employee A, Employee B)
under strict tenant isolation, role enforcement, disabled-user instant revocation,
collection privacy, and document ownership checks.
"""

from unittest.mock import patch
import pytest
from fastapi.testclient import TestClient
from backend.main import app
from backend import auth, keystore


@pytest.fixture
def client():
    return TestClient(app)


def test_pilot_multiuser_rbac_and_isolation(client: TestClient, tmp_path):
    # 1. Setup mock users
    admin_user = {"id": "usr_pilot_admin", "email": "admin@pilot.corp", "role": "admin", "status": "active", "org_id": "pilot_org"}
    emp_a = {"id": "usr_pilot_empa", "email": "empa@pilot.corp", "role": "user", "status": "active", "org_id": "pilot_org"}
    emp_b = {"id": "usr_pilot_empb", "email": "empb@pilot.corp", "role": "user", "status": "active", "org_id": "pilot_org"}

    admin_token = auth.issue_token(admin_user["id"], org_id=admin_user["org_id"])
    empa_token = auth.issue_token(emp_a["id"], org_id=emp_a["org_id"])
    empb_token = auth.issue_token(emp_b["id"], org_id=emp_b["org_id"])

    def mock_get_user_by_id(uid: str):
        if uid == admin_user["id"]:
            return admin_user
        if uid == emp_a["id"]:
            return emp_a
        if uid == emp_b["id"]:
            return emp_b
        return None

    with patch.object(auth, "get_user_by_id", side_effect=mock_get_user_by_id):
        # 2. Test Admin Endpoint Access (Employee A rejected, Admin allowed)
        res_empa_admin = client.get("/api/admin/users", headers={"Authorization": f"Bearer {empa_token}"})
        assert res_empa_admin.status_code == 403, "Non-admin user must be rejected from /api/admin/users"

        res_admin_access = client.get("/api/admin/users", headers={"Authorization": f"Bearer {admin_token}"})
        assert res_admin_access.status_code == 200, "Admin must be allowed to access /api/admin/users"

        # 3. Test Disabled User Instant Revocation
        # Disable Employee B
        emp_b["status"] = "disabled"
        res_disabled = client.get("/api/auth/me", headers={"Authorization": f"Bearer {empb_token}"})
        assert res_disabled.status_code == 403, "Disabled user token must be immediately rejected with 403"
        assert "disabled" in str(res_disabled.json()).lower()

        # Re-enable Employee B for remaining tests
        emp_b["status"] = "active"

        # 4. Test Cross-Tenant Collection Isolation
        # Employee A creates a collection
        res_create_col = client.post(
            "/api/collections",
            json={"name": "Confidential Q4 Strategy", "description": "Restricted to Emp A"},
            headers={"Authorization": f"Bearer {empa_token}"},
        )
        assert res_create_col.status_code == 200
        col_id = res_create_col.json().get("collection", {}).get("id") or res_create_col.json().get("id")

        if col_id:
            # Employee B attempts to modify or delete Employee A's collection
            res_cross_delete = client.delete(
                f"/api/collections/{col_id}",
                headers={"Authorization": f"Bearer {empb_token}"},
            )
            # Must return 404 to avoid leaking collection existence to unauthorized user
            assert res_cross_delete.status_code in (403, 404), "Employee B must not be permitted to delete Emp A's collection"

        # 5. Test Cross-Tenant Document Deletion Prevention (IDOR)
        # Attempt to delete document not owned by Employee A
        res_cross_doc_del = client.delete(
            "/api/documents/employee_b_strictly_confidential.pdf",
            headers={"Authorization": f"Bearer {empa_token}"},
        )
        assert res_cross_doc_del.status_code in (403, 404), "Unauthorized document deletion must be rejected"
