"""
Per-user encrypted API key storage.

Keys are encrypted with Fernet (AES-128-CBC + HMAC-SHA256).  The Fernet
master key is generated once and stored in config.KEYS_SECRET_FILE; the
encrypted per-user keys live in config.PROVIDER_KEYS_FILE as JSON.

Layout of provider_keys.json:
    {
        "<user_id>": {
            "gemini":    "<fernet-token>",
            "openai":    "<fernet-token>",
            ...
        }
    }
"""

from __future__ import annotations

import json
import threading
from pathlib import Path
from typing import Dict, Optional

from cryptography.fernet import Fernet, InvalidToken

from backend import config

_lock = threading.Lock()


# ------------------------------------------------------------------ master key

def _load_or_create_fernet() -> Fernet:
    path: Path = config.KEYS_SECRET_FILE
    if path.exists():
        return Fernet(path.read_bytes().strip())
    key = Fernet.generate_key()
    path.write_bytes(key)
    return Fernet(key)


_fernet: Optional[Fernet] = None


def _get_fernet() -> Fernet:
    global _fernet
    if _fernet is None:
        _fernet = _load_or_create_fernet()
    return _fernet


# ------------------------------------------------------------------ JSON store

def _read_store() -> Dict:
    p: Path = config.PROVIDER_KEYS_FILE
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def _write_store(data: Dict) -> None:
    config.PROVIDER_KEYS_FILE.write_text(
        json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8"
    )


# ------------------------------------------------------------------ public API

def set_key(user_id: str, provider: str, plaintext_key: str) -> None:
    """Encrypt and persist an API key for (user_id, provider)."""
    token = _get_fernet().encrypt(plaintext_key.encode()).decode()
    with _lock:
        store = _read_store()
        store.setdefault(user_id, {})[provider] = token
        _write_store(store)


def get_key(user_id: str, provider: str) -> Optional[str]:
    """Return the decrypted API key, or None if not set / corrupted."""
    with _lock:
        store = _read_store()
    token = store.get(user_id, {}).get(provider)
    if not token:
        return None
    try:
        return _get_fernet().decrypt(token.encode()).decode()
    except InvalidToken:
        return None


def delete_key(user_id: str, provider: str) -> None:
    """Remove the stored key for (user_id, provider)."""
    with _lock:
        store = _read_store()
        if user_id in store and provider in store[user_id]:
            del store[user_id][provider]
            if not store[user_id]:
                del store[user_id]
            _write_store(store)


def has_key(user_id: str, provider: str) -> bool:
    """Return True if a (possibly corrupted) token exists for this pair."""
    with _lock:
        store = _read_store()
    return bool(store.get(user_id, {}).get(provider))


def list_providers_with_keys(user_id: str) -> list[str]:
    """Return provider names that have a stored key for this user."""
    with _lock:
        store = _read_store()
    return list(store.get(user_id, {}).keys())
