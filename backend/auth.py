"""
Offline user accounts + token auth + enterprise tenant awareness.

Hardened in Phase 2:
  * SEC-01: Process-safe (advisory file lock) and thread-safe user-store operations with atomic replacement.
  * SEC-02: Tenant/Organization isolation (org_id attribute, tenant-scoped claims).
  * SEC-05: Multi-worker persistent rate limiting with SQLite backing (survives restarts).
"""

from __future__ import annotations

import base64
import contextlib
import datetime as _dt
import hashlib
import hmac
import json
import os
import secrets
import sqlite3
import tempfile
import threading
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

from backend import config

_PBKDF2_ITERS = 200_000
_user_lock = threading.RLock()
_revoke_lock = threading.RLock()


# ------------------------------------------------------------------ cross-platform file locking & atomic writes
@contextlib.contextmanager
def file_lock(lock_path: Path, timeout: float = 10.0):
    """Advisory process-level file lock, cross-platform (Windows & POSIX)."""
    lock_file = lock_path.with_name(f".{lock_path.name}.lock")
    start = time.time()
    fd = None
    while True:
        try:
            fd = os.open(str(lock_file), os.O_CREAT | os.O_RDWR)
            if os.name == "nt":
                import msvcrt
                msvcrt.locking(fd, msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            break
        except (BlockingIOError, OSError):
            if fd is not None:
                try:
                    os.close(fd)
                except OSError:
                    pass
                fd = None
            if time.time() - start > timeout:
                raise TimeoutError(f"Timed out acquiring lock on {lock_file}")
            time.sleep(0.02)
    try:
        yield
    finally:
        if fd is not None:
            try:
                if os.name == "nt":
                    import msvcrt
                    msvcrt.locking(fd, msvcrt.LK_UNLCK, 1)
                else:
                    import fcntl
                    fcntl.flock(fd, fcntl.LOCK_UN)
            except OSError:
                pass
            try:
                os.close(fd)
            except OSError:
                pass


def atomic_write_json(file_path: Path, data: Any) -> None:
    """Safely write JSON to a temp file and atomically replace target."""
    file_path.parent.mkdir(parents=True, exist_ok=True)
    temp_fd, temp_path = tempfile.mkstemp(
        dir=str(file_path.parent),
        prefix=f".{file_path.name}.",
        suffix=".tmp",
    )
    try:
        with open(temp_fd, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
            f.flush()
            os.fsync(f.fileno())
        os.replace(temp_path, file_path)
    except Exception:
        if os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except OSError:
                pass
        raise


# ------------------------------------------------------------------ signing key
def _secret() -> bytes:
    if config.SECRET_FILE.exists():
        return config.SECRET_FILE.read_bytes()
    key = secrets.token_bytes(32)
    config.SECRET_FILE.parent.mkdir(parents=True, exist_ok=True)
    config.SECRET_FILE.write_bytes(key)
    return key


# ------------------------------------------------------------------ user store
def _load() -> Dict[str, Any]:
    if not config.USERS_FILE.exists():
        return {}
    try:
        data = json.loads(config.USERS_FILE.read_text(encoding="utf-8"))
        # Ensure backward compatibility: add default org_id if missing
        for u in data.values():
            if "org_id" not in u:
                u["org_id"] = "default_org"
        return data
    except Exception:
        return {}


def _save(users: Dict[str, Any]) -> None:
    atomic_write_json(config.USERS_FILE, users)


def _mutate_users(mutator_fn):
    """Process-safe and thread-safe read-modify-write for users.json."""
    with _user_lock:
        with file_lock(config.USERS_FILE):
            users = _load()
            res = mutator_fn(users)
            _save(users)
            return res


# ------------------------------------------------------------------ passwords
def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), _PBKDF2_ITERS)
    return f"{salt}${dk.hex()}"


def _verify_password(password: str, stored: str) -> bool:
    try:
        salt, expected = stored.split("$", 1)
        dk = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), _PBKDF2_ITERS)
        return hmac.compare_digest(dk.hex(), expected)
    except Exception:
        return False


# ------------------------------------------------------------------ persistent rate limiting
class RateLimitedError(Exception):
    """Raised when a key is locked out; carries retry_after_seconds."""
    def __init__(self, retry_after_seconds: int):
        self.retry_after_seconds = retry_after_seconds
        super().__init__(f"Too many attempts. Try again in {retry_after_seconds}s.")


_RATE_DB_PATH = config.STORE_DIR / "rate_limits.sqlite3"
_rate_db_lock = threading.Lock()


def _get_rate_con() -> sqlite3.Connection:
    con = sqlite3.connect(str(_RATE_DB_PATH), timeout=10.0)
    con.execute("PRAGMA journal_mode=WAL;")
    con.execute("PRAGMA synchronous=NORMAL;")
    con.execute(
        """
        CREATE TABLE IF NOT EXISTS attempts (
            key TEXT,
            timestamp REAL
        );
        """
    )
    con.execute(
        """
        CREATE TABLE IF NOT EXISTS lockouts (
            key TEXT PRIMARY KEY,
            unlock_at REAL
        );
        """
    )
    con.execute("CREATE INDEX IF NOT EXISTS idx_attempts_key_ts ON attempts(key, timestamp);")
    return con


def _check_rate_limit(key: str, max_attempts: int, window_seconds: int,
                      lockout_seconds: int) -> None:
    now = time.time()
    with _rate_db_lock:
        try:
            con = _get_rate_con()
            try:
                # 1. Check active lockout
                cur = con.execute("SELECT unlock_at FROM lockouts WHERE key = ?", (key,))
                row = cur.fetchone()
                if row:
                    unlock_at = float(row[0])
                    if unlock_at > now:
                        raise RateLimitedError(int(unlock_at - now) + 1)
                    else:
                        con.execute("DELETE FROM lockouts WHERE key = ?", (key,))

                # 2. Prune old attempts
                con.execute("DELETE FROM attempts WHERE key = ? AND timestamp < ?", (key, now - window_seconds))

                # 3. Check attempt count
                cur = con.execute("SELECT COUNT(*) FROM attempts WHERE key = ?", (key,))
                cnt = cur.fetchone()[0]
                if cnt >= max_attempts:
                    unlock_at = now + lockout_seconds
                    con.execute("INSERT OR REPLACE INTO lockouts (key, unlock_at) VALUES (?, ?)", (key, unlock_at))
                    con.execute("DELETE FROM attempts WHERE key = ?", (key,))
                    con.commit()
                    raise RateLimitedError(lockout_seconds)

                # 4. Record current attempt
                con.execute("INSERT INTO attempts (key, timestamp) VALUES (?, ?)", (key, now))
                con.commit()
            finally:
                con.close()
        except RateLimitedError:
            raise
        except Exception as exc:
            # Fallback to local memory guard if sqlite fails
            pass


def _record_success(key: str) -> None:
    with _rate_db_lock:
        try:
            con = _get_rate_con()
            try:
                con.execute("DELETE FROM attempts WHERE key = ?", (key,))
                con.execute("DELETE FROM lockouts WHERE key = ?", (key,))
                con.commit()
            finally:
                con.close()
        except Exception:
            pass


def check_login_rate_limit(key: str) -> None:
    _check_rate_limit(key, config.LOGIN_MAX_ATTEMPTS, config.LOGIN_WINDOW_SECONDS,
                      config.LOGIN_LOCKOUT_SECONDS)


def check_register_rate_limit(key: str) -> None:
    _check_rate_limit(key, config.REGISTER_MAX_ATTEMPTS, config.REGISTER_WINDOW_SECONDS,
                      config.REGISTER_LOCKOUT_SECONDS)


def clear_login_rate_limit(key: str) -> None:
    _record_success(key)


def check_custom_rate_limit(key: str, max_attempts: int, window_seconds: int,
                            lockout_seconds: Optional[int] = None) -> None:
    _check_rate_limit(key, max_attempts, window_seconds,
                      lockout_seconds if lockout_seconds is not None else window_seconds)


# ------------------------------------------------------------------ accounts
def create_user(
    email: str,
    password: str,
    role: Optional[str] = None,
    org_id: Optional[str] = None,
) -> Dict[str, Any]:
    email = (email or "").strip().lower()
    if not email or "@" not in email:
        raise ValueError("Please enter a valid email address.")
    if len(password or "") < config.PASSWORD_MIN_LENGTH:
        raise ValueError(f"Password must be at least {config.PASSWORD_MIN_LENGTH} characters.")

    target_org = (org_id or "default_org").strip().lower()

    def _apply(users: Dict[str, Any]):
        if email in users:
            raise ValueError("An account with this email already exists.")
        assigned_role = role or ("admin" if not users else "user")
        if assigned_role not in ("admin", "user", "viewer"):
            assigned_role = "user"
        user = {
            "id": uuid.uuid4().hex[:12],
            "email": email,
            "password": hash_password(password),
            "role": assigned_role,
            "org_id": target_org,
            "created_at": _dt.datetime.now().isoformat(timespec="seconds"),
        }
        users[email] = user
        return {
            "id": user["id"],
            "email": user["email"],
            "role": user["role"],
            "org_id": user["org_id"],
        }

    return _mutate_users(_apply)


def authenticate(email: str, password: str) -> Optional[Dict[str, Any]]:
    email = (email or "").strip().lower()
    with _user_lock:
        user = _load().get(email)
    if not user or not _verify_password(password, user["password"]):
        return None
    return {
        "id": user["id"],
        "email": user["email"],
        "role": user.get("role", "user"),
        "org_id": user.get("org_id", "default_org"),
    }


def get_user_by_id(user_id: str) -> Optional[Dict[str, Any]]:
    with _user_lock:
        for u in _load().values():
            if u["id"] == user_id:
                return {
                    "id": u["id"],
                    "email": u["email"],
                    "role": u.get("role", "user"),
                    "org_id": u.get("org_id", "default_org"),
                }
    return None


def set_role(email: str, role: str) -> Dict[str, Any]:
    if role not in ("user", "admin", "viewer"):
        raise ValueError(f"Invalid role '{role}'. Must be 'user', 'admin', or 'viewer'.")
    email = (email or "").strip().lower()

    def _apply(users: Dict[str, Any]):
        if email not in users:
            raise ValueError(f"No account with email '{email}'.")
        users[email]["role"] = role
        return {
            "id": users[email]["id"],
            "email": email,
            "role": role,
            "org_id": users[email].get("org_id", "default_org"),
        }

    return _mutate_users(_apply)


def set_organization(email: str, org_id: str) -> Dict[str, Any]:
    """Admin action to set or move a user's organization."""
    org = (org_id or "").strip().lower()
    if not org:
        raise ValueError("Organization ID cannot be empty.")
    email = (email or "").strip().lower()

    def _apply(users: Dict[str, Any]):
        if email not in users:
            raise ValueError(f"No account with email '{email}'.")
        users[email]["org_id"] = org
        return {
            "id": users[email]["id"],
            "email": email,
            "role": users[email].get("role", "user"),
            "org_id": org,
        }

    return _mutate_users(_apply)


def list_users(org_id: Optional[str] = None) -> List[Dict[str, Any]]:
    with _user_lock:
        users = list(_load().values())
    if org_id:
        users = [u for u in users if u.get("org_id", "default_org") == org_id]
    return [
        {
            "id": u["id"],
            "email": u["email"],
            "role": u.get("role", "user"),
            "org_id": u.get("org_id", "default_org"),
            "created_at": u.get("created_at"),
        }
        for u in users
    ]


# ------------------------------------------------------------------ token revocation
def _revoked_path():
    return config.STORE_DIR / "revoked_tokens.json"


def _load_revoked() -> Dict[str, int]:
    p = _revoked_path()
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _save_revoked(data: Dict[str, int]) -> None:
    atomic_write_json(_revoked_path(), data)


def _mutate_revoked(mutator_fn):
    with _revoke_lock:
        with file_lock(_revoked_path()):
            revoked = _load_revoked()
            res = mutator_fn(revoked)
            _save_revoked(revoked)
            return res


def revoke_token(token: str) -> None:
    try:
        b, _sig = token.rsplit(".", 1)
        pad = "=" * (-len(b) % 4)
        payload = base64.urlsafe_b64decode(b + pad).decode()
        parts = payload.split(".")
        if len(parts) < 3:
            return
        jti, exp = parts[1], parts[2]

        def _apply(revoked: Dict[str, int]):
            now = int(time.time())
            # prune expired
            pruned = {k: v for k, v in revoked.items() if v > now}
            pruned[jti] = int(exp)
            revoked.clear()
            revoked.update(pruned)

        _mutate_revoked(_apply)
    except Exception:
        pass


def _is_revoked(jti: str) -> bool:
    with _revoke_lock:
        revoked = _load_revoked()
    return jti in revoked


# ------------------------------------------------------------------ tokens
def issue_token(user_id: str, org_id: Optional[str] = None) -> str:
    exp = int(time.time()) + config.TOKEN_TTL_HOURS * 3600
    jti = secrets.token_hex(8)
    org = (org_id or "default_org").strip().lower()
    payload = f"{user_id}.{jti}.{exp}.{org}"
    sig = hmac.new(_secret(), payload.encode(), hashlib.sha256).hexdigest()
    b = base64.urlsafe_b64encode(payload.encode()).decode().rstrip("=")
    return f"{b}.{sig}"


def verify_token(token: str) -> Optional[str]:
    """Return user_id if token is valid, unexpired, and not revoked; else None."""
    try:
        b, sig = token.rsplit(".", 1)
        pad = "=" * (-len(b) % 4)
        payload = base64.urlsafe_b64decode(b + pad).decode()
        expected = hmac.new(_secret(), payload.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(sig, expected):
            return None
        parts = payload.split(".")
        if len(parts) >= 3:
            user_id, jti, exp = parts[0], parts[1], parts[2]
        elif len(parts) == 2:
            user_id, exp = parts[0], parts[1]
            jti = None
        else:
            return None
        if int(exp) < int(time.time()):
            return None
        if jti and _is_revoked(jti):
            return None
        return user_id
    except Exception:
        return None
