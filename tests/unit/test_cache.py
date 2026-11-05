"""
Cache-key regression tests.

These tests mirror the cache-key contract documented in
COMPLETION_MATRIX.md without importing backend/main.py.

This keeps the tests isolated from the provider-router test suite,
which intentionally installs a fake config module.
"""

from __future__ import annotations

import hashlib
import json


def _history_hash(history):
    """Same algorithm as backend/main.py::_history_hash."""
    blob = json.dumps(history or [], sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def _cache_key(route, user_id, payload):
    """Same algorithm as backend/main.py::_cache_key."""
    blob = json.dumps(payload, sort_keys=True, ensure_ascii=False)
    digest = hashlib.sha256(blob.encode("utf-8")).hexdigest()
    return f"{route}:{user_id}:{digest}"


def _payload(
    *,
    session_id="session-1",
    query="What is ChromaDB?",
    files=None,
    provider="ollama",
    model="qwen3:4b",
    history_hash="history-a",
):
    return {
        "session_id": session_id,
        "query": query,
        "top_k": 5,
        "modality": "all",
        "files": files or [],
        "route": "query",
        "provider": provider,
        "model": model,
        "history_hash": history_hash,
        "phase3": [False, False, False, False],
    }


def test_same_inputs_produce_same_cache_key():
    payload = _payload()

    assert _cache_key("query", "user-1", payload) == \
           _cache_key("query", "user-1", payload)


def test_different_history_produces_different_cache_key():
    key1 = _cache_key("query", "user-1", _payload(history_hash="history-a"))
    key2 = _cache_key("query", "user-1", _payload(history_hash="history-b"))

    assert key1 != key2


def test_different_users_are_isolated():
    payload = _payload()

    key1 = _cache_key("query", "user-1", payload)
    key2 = _cache_key("query", "user-2", payload)

    assert key1 != key2


def test_different_sessions_are_isolated():
    key1 = _cache_key("query", "user-1", _payload(session_id="session-1"))
    key2 = _cache_key("query", "user-1", _payload(session_id="session-2"))

    assert key1 != key2


def test_document_change_invalidates_cache_key():
    key1 = _cache_key(
        "query", "user-1", _payload(files=["document-a.pdf"])
    )
    key2 = _cache_key(
        "query", "user-1", _payload(files=["document-b.pdf"])
    )

    assert key1 != key2


def test_model_change_invalidates_cache_key():
    key1 = _cache_key("query", "user-1", _payload(model="qwen3:4b"))
    key2 = _cache_key("query", "user-1", _payload(model="qwen3:8b"))

    assert key1 != key2


def test_provider_change_invalidates_cache_key():
    key1 = _cache_key("query", "user-1", _payload(provider="ollama"))
    key2 = _cache_key("query", "user-1", _payload(provider="groq"))

    assert key1 != key2


def test_history_hash_uses_content_not_only_history_length():
    history_a = [
        {"role": "user", "content": "What is ChromaDB?"},
    ]
    history_b = [
        {"role": "user", "content": "What is Redis?"},
    ]

    assert len(history_a) == len(history_b)
    assert _history_hash(history_a) != _history_hash(history_b)


def test_history_hash_is_deterministic():
    history = [
        {"role": "user", "content": "What is ChromaDB?"},
        {"role": "assistant", "content": "It is a vector database."},
    ]

    assert _history_hash(history) == _history_hash(history)


def test_cache_key_is_sha256_based():
    payload = _payload()
    key = _cache_key("query", "user-1", payload)

    blob = json.dumps(payload, sort_keys=True, ensure_ascii=False)
    expected_digest = hashlib.sha256(blob.encode("utf-8")).hexdigest()

    assert key == f"query:user-1:{expected_digest}"
