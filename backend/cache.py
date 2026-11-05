from __future__ import annotations

import collections
import json
import threading
import time
from typing import Any, Dict, Optional, Tuple

import redis

from backend import config
from backend.observability import metrics as obs_metrics

_client: Optional[redis.Redis] = None
_client_checked: bool = False

# Thread-safe in-memory LRU cache for offline environments (Phase 3 Performance)
MAX_LOCAL_CACHE_ENTRIES = 1000
_local_lru: collections.OrderedDict[str, Tuple[Any, float]] = collections.OrderedDict()
_local_lock = threading.Lock()


def _get_client() -> Optional[redis.Redis]:
    global _client, _client_checked
    if _client_checked:
        return _client
    if not config.CACHE_ENABLED:
        _client_checked = True
        return None
    try:
        client = redis.Redis.from_url(config.REDIS_URL, decode_responses=True, socket_connect_timeout=0.2)
        client.ping()
        _client = client
    except Exception:
        _client = None
    finally:
        _client_checked = True
    return _client


def is_available() -> bool:
    """Returns True if caching is operational (either Redis or local LRU)."""
    return True


def is_redis_available() -> bool:
    """Returns True specifically if external Redis is online."""
    return _get_client() is not None


def get_json(key: str) -> Any:
    # 1. Try Redis first if available
    client = _get_client()
    if client is not None:
        try:
            raw = client.get(key)
            if raw:
                value = json.loads(raw)
                obs_metrics.inc_counter("cache_hits_total")
                return value
        except Exception:
            pass

    # 2. In-memory LRU cache fallback
    now = time.monotonic()
    with _local_lock:
        if key in _local_lru:
            val, expires_at = _local_lru[key]
            if expires_at > now:
                _local_lru.move_to_end(key)
                obs_metrics.inc_counter("cache_hits_total")
                return val
            else:
                del _local_lru[key]

    obs_metrics.inc_counter("cache_misses_total")
    return None


def set_json(key: str, value: Any, ttl_seconds: Optional[int] = None) -> None:
    ttl = ttl_seconds or config.CACHE_TTL_SECONDS
    # 1. Try Redis
    client = _get_client()
    if client is not None:
        try:
            client.set(key, json.dumps(value, ensure_ascii=False), ex=ttl)
        except Exception:
            pass

    # 2. Local in-memory LRU
    now = time.monotonic()
    expires_at = now + ttl
    with _local_lock:
        if key in _local_lru:
            _local_lru.move_to_end(key)
        _local_lru[key] = (value, expires_at)
        while len(_local_lru) > MAX_LOCAL_CACHE_ENTRIES:
            _local_lru.popitem(last=False)


def delete_prefix(prefix: str) -> None:
    # 1. Purge Redis
    client = _get_client()
    if client is not None:
        try:
            for key in client.scan_iter(match=f"{prefix}*"):
                client.delete(key)
        except Exception:
            pass

    # 2. Purge local LRU
    with _local_lock:
        matching = [k for k in _local_lru if k.startswith(prefix)]
        for k in matching:
            del _local_lru[k]


def clear_local_cache() -> None:
    with _local_lock:
        _local_lru.clear()
