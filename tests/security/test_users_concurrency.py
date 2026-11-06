import concurrent.futures
import shutil
import tempfile
from pathlib import Path
import pytest

from backend import auth, config


@pytest.fixture(autouse=True)
def isolated_user_store(monkeypatch):
    """Isolate users.json and rate_limits.sqlite3 to a temp directory for concurrency tests."""
    temp_dir = Path(tempfile.mkdtemp(prefix="test_auth_concurrency_"))
    test_users_file = temp_dir / "users.json"
    test_secret_file = temp_dir / "secret.key"
    test_rate_db = temp_dir / "rate_limits.sqlite3"
    test_revoked_file = temp_dir / "revoked_tokens.json"

    monkeypatch.setattr(config, "STORE_DIR", temp_dir)
    monkeypatch.setattr(config, "USERS_FILE", test_users_file)
    monkeypatch.setattr(config, "SECRET_FILE", test_secret_file)
    monkeypatch.setattr(auth, "_RATE_DB_PATH", test_rate_db)

    yield temp_dir
    shutil.rmtree(temp_dir, ignore_errors=True)


def test_concurrent_registrations_no_data_loss():
    """Verify 20 concurrent threads registering distinct accounts suffer 0 race-condition data loss."""
    num_users = 20
    emails = [f"user_{i}@enterprise.corp" for i in range(num_users)]
    password = "StrongPassword123!"

    def _register(email):
        return auth.create_user(email, password, org_id="acme_corp")

    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        results = list(executor.map(_register, emails))

    assert len(results) == num_users
    registered_ids = {r["id"] for r in results}
    assert len(registered_ids) == num_users

    # Verify all users exist on disk and can authenticate
    users = auth._load()
    assert len(users) == num_users

    for email in emails:
        user = auth.authenticate(email, password)
        assert user is not None
        assert user["email"] == email
        assert user["org_id"] == "acme_corp"


def test_concurrent_duplicate_registration_handled_cleanly():
    """Verify concurrent registration attempts for the same email fail cleanly with only 1 winner."""
    email = "duplicate@enterprise.corp"
    password = "SecurePassword987!"

    def _register_attempt(_):
        try:
            return auth.create_user(email, password)
        except ValueError:
            return None

    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
        results = list(executor.map(_register_attempt, range(10)))

    successful = [r for r in results if r is not None]
    assert len(successful) == 1
    assert auth.authenticate(email, password) is not None

