"""
Offline user accounts + token auth.

Uses ONLY the Python standard library + one revocation-list file:
  * passwords hashed with PBKDF2-HMAC-SHA256 + a per-user random salt,
  * login returns an HMAC-signed, expiring token (like a mini-JWT) that also
    carries a random per-token id (jti) so a single token can be revoked
    (logout) without affecting the user's other sessions/devices.

Everything is local: users live in storage/users.json, the signing key in
storage/secret.key, revoked token ids in storage/revoked_tokens.json. This
gives each person a private space — one user can never see another's files
or chats.

AUDIT_REPORT.md fixes in this file:
  P0-3  login/registration rate limiting + lockout backoff
  P0-4  token revocation (logout invalidates a token immediately, not just
        at its natural TTL)
  P1-5  stronger password policy (config.PASSWORD_MIN_LENGTH, default 8)
"""

from __future__ import annotations

import base64
import datetime as _dt
import hashlib
import hmac
import json
import secrets
import threading
import time
import uuid
from typing import Any, Dict, List, Optional

from backend import config

_PBKDF2_ITERS = 200_000


# ------------------------------------------------------------------ signing key
def _secret() -> bytes:
    if config.SECRET_FILE.exists():
        return config.SECRET_FILE.read_bytes()
    key = secrets.token_bytes(32)
    config.SECRET_FILE.write_bytes(key)
    return key


# ------------------------------------------------------------------ user store
def _load() -> Dict[str, Any]:
    if not config.USERS_FILE.exists():
        return {}
    try:
        return json.loads(config.USERS_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _save(users: Dict[str, Any]) -> None:
    config.USERS_FILE.write_text(json.dumps(users, ensure_ascii=False, indent=2),
                                 encoding="utf-8")


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


# ------------------------------------------------------------------ rate limiting
# In-process, per-key (email or IP) sliding-window counter + lockout. This is
# adequate for a single-process local/desktop deployment (this app's actual
# architecture — see AUDIT_REPORT.md §1); a multi-process production
# deployment should back this with Redis instead (brief §27), same as the
# existing query-cache layer already does.
_attempt_lock = threading.Lock()
_attempts: Dict[str, list] = {}          # key -> [timestamps]
_lockouts: Dict[str, float] = {}         # key -> unlock_at (epoch seconds)


class RateLimitedError(Exception):
    """Raised when a key is locked out; carries retry_after_seconds."""
    def __init__(self, retry_after_seconds: int):
        self.retry_after_seconds = retry_after_seconds
        super().__init__(f"Too many attempts. Try again in {retry_after_seconds}s.")


def _check_rate_limit(key: str, max_attempts: int, window_seconds: int,
                      lockout_seconds: int) -> None:
    now = time.time()
    with _attempt_lock:
        unlock_at = _lockouts.get(key)
        if unlock_at and unlock_at > now:
            raise RateLimitedError(int(unlock_at - now) + 1)
        if unlock_at and unlock_at <= now:
            _lockouts.pop(key, None)
            _attempts.pop(key, None)

        history = [t for t in _attempts.get(key, []) if now - t < window_seconds]
        if len(history) >= max_attempts:
            _lockouts[key] = now + lockout_seconds
            _attempts[key] = []
            raise RateLimitedError(lockout_seconds)
        history.append(now)
        _attempts[key] = history


def _record_success(key: str) -> None:
    with _attempt_lock:
        _attempts.pop(key, None)
        _lockouts.pop(key, None)


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
    """General-purpose limiter for non-auth endpoints (chat/ingest —
    AUDIT_REPORT.md P2-5 / brief §27). Reuses the same sliding-window +
    lockout mechanism as login/register."""
    _check_rate_limit(key, max_attempts, window_seconds,
                      lockout_seconds if lockout_seconds is not None else window_seconds)


# ------------------------------------------------------------------ accounts
def create_user(email: str, password: str) -> Dict[str, Any]:
    email = (email or "").strip().lower()
    if not email or "@" not in email:
        raise ValueError("Please enter a valid email address.")
    if len(password or "") < config.PASSWORD_MIN_LENGTH:
        raise ValueError(f"Password must be at least {config.PASSWORD_MIN_LENGTH} characters.")
    users = _load()
    if email in users:
        raise ValueError("An account with this email already exists.")
    # brief §24: minimal RBAC. The very first account on a fresh install
    # becomes admin automatically — a common, sensible bootstrap for a
    # self-hosted app (no separate invite flow needed, no manual file
    # editing required) — every account after that defaults to "user".
    # This is a one-time, install-time decision: promoting/demoting
    # anyone later is a deliberate admin action, not something this
    # function does again.
    role = "admin" if not users else "user"
    user = {
        "id": uuid.uuid4().hex[:12],
        "email": email,
        "password": hash_password(password),
        "role": role,
        "created_at": _dt.datetime.now().isoformat(timespec="seconds"),
    }
    users[email] = user
    _save(users)
    return {"id": user["id"], "email": user["email"], "role": role}


def authenticate(email: str, password: str) -> Optional[Dict[str, Any]]:
    email = (email or "").strip().lower()
    user = _load().get(email)
    if not user or not _verify_password(password, user["password"]):
        return None
    return {"id": user["id"], "email": user["email"], "role": user.get("role", "user")}


def get_user_by_id(user_id: str) -> Optional[Dict[str, Any]]:
    for u in _load().values():
        if u["id"] == user_id:
            return {"id": u["id"], "email": u["email"], "role": u.get("role", "user")}
    return None


def set_role(email: str, role: str) -> Dict[str, Any]:
    """Admin action (brief §24's authorization matrix: "User management:
    Admin only"). Callers (main.py's admin endpoint) are responsible for
    checking the CALLER is an admin before invoking this — this function
    only enforces that `role` itself is a valid value."""
    if role not in ("user", "admin"):
        raise ValueError(f"Invalid role '{role}'. Must be 'user' or 'admin'.")
    email = (email or "").strip().lower()
    users = _load()
    if email not in users:
        raise ValueError(f"No account with email '{email}'.")
    users[email]["role"] = role
    _save(users)
    return {"id": users[email]["id"], "email": email, "role": role}


def list_users() -> List[Dict[str, Any]]:
    """Admin action — never includes password hashes (brief §54/§36-style
    'never log/return secrets' applies to this listing too)."""
    return [
        {"id": u["id"], "email": u["email"], "role": u.get("role", "user"),
         "created_at": u.get("created_at")}
        for u in _load().values()
    ]


# ------------------------------------------------------------------ token revocation
# A tiny JSON set of revoked token ids (jti), pruned of anything already
# past its natural expiry so the file never grows without bound.
_revoke_lock = threading.Lock()


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
    _revoked_path().write_text(json.dumps(data), encoding="utf-8")


def revoke_token(token: str) -> None:
    """Invalidate one token immediately (logout), without touching the
    user's other active sessions/devices."""
    try:
        b, _sig = token.rsplit(".", 1)
        pad = "=" * (-len(b) % 4)
        payload = base64.urlsafe_b64decode(b + pad).decode()
        parts = payload.split(".")
        if len(parts) < 3:
            return
        jti, exp = parts[1], parts[2]
        with _revoke_lock:
            revoked = _load_revoked()
            now = int(time.time())
            revoked = {k: v for k, v in revoked.items() if v > now}  # prune expired
            revoked[jti] = int(exp)
            _save_revoked(revoked)
    except Exception:
        pass


def _is_revoked(jti: str) -> bool:
    with _revoke_lock:
        revoked = _load_revoked()
    return jti in revoked


# ------------------------------------------------------------------ tokens
def issue_token(user_id: str) -> str:
    exp = int(time.time()) + config.TOKEN_TTL_HOURS * 3600
    jti = secrets.token_hex(8)
    payload = f"{user_id}.{jti}.{exp}"
    sig = hmac.new(_secret(), payload.encode(), hashlib.sha256).hexdigest()
    b = base64.urlsafe_b64encode(payload.encode()).decode().rstrip("=")
    return f"{b}.{sig}"


def verify_token(token: str) -> Optional[str]:
    """Return the user_id if the token is valid, unexpired, and not
    revoked; else None."""
    try:
        b, sig = token.rsplit(".", 1)
        pad = "=" * (-len(b) % 4)
        payload = base64.urlsafe_b64decode(b + pad).decode()
        expected = hmac.new(_secret(), payload.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(sig, expected):
            return None
        parts = payload.split(".")
        if len(parts) == 3:
            user_id, jti, exp = parts
        elif len(parts) == 2:
            # Backward-compat with tokens issued before jti was added.
            user_id, exp = parts
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
