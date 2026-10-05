from __future__ import annotations

import json
from typing import Any, Optional

import redis

from backend import config
from backend.observability import metrics as obs_metrics

_client: Optional[redis.Redis] = None

def _get_client() -> Optional[redis.Redis]:
    global _client
    if _client is not None:
        return _client
    if not config.CACHE_ENABLED:
        return None
    try:
        client = redis.Redis.from_url(config.REDIS_URL, decode_responses=True)
        client.ping()
        _client = client
        return _client
    except Exception:
        _client = None
        return None

def is_available() -> bool:
    """Used by /health/dependencies (brief §56) — a noncritical dependency
    check, not a liveness check: the app works without Redis (cache.py
    degrades to no-op everywhere above), so this reports status, it never
    raises."""
    return _get_client() is not None

def get_json(key: str) -> Any:
    client = _get_client()
    if client is None:
        return None
    raw = client.get(key)
    if not raw:
        obs_metrics.inc_counter("cache_misses_total")
        return None
    try:
        value = json.loads(raw)
        obs_metrics.inc_counter("cache_hits_total")
        return value
    except Exception:
        obs_metrics.inc_counter("cache_misses_total")
        return None

def set_json(key: str, value: Any, ttl_seconds: Optional[int] = None) -> None:
    client = _get_client()
    if client is None:
        return
    try:
        client.set(key, json.dumps(value, ensure_ascii=False), ex=ttl_seconds or config.CACHE_TTL_SECONDS)
    except Exception:
        pass

def delete_prefix(prefix: str) -> None:
    client = _get_client()
    if client is None:
        return
    try:
        for key in client.scan_iter(match=f"{prefix}*"):
            client.delete(key)
    except Exception:
        pass