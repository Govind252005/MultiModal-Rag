"""
Per-provider circuit breaker (transformation brief §98).

Scope, deliberately narrow: this only trips on error categories that
indicate the PROVIDER itself is unhealthy — "provider_unavailable" (5xx)
and "network_error" (can't connect at all). It never trips on
"invalid_api_key", "invalid_request", or "rate_limited": those are about
one user's key/request/quota, not the provider's health, and tripping a
process-wide breaker because one user has a bad key would incorrectly
lock every other user out of a provider that's actually fine. Getting
this scoping wrong is worse than not having a circuit breaker at all, so
it's called out explicitly here and in the one place this module is used
(router.py).

States, standard circuit-breaker shape:
    CLOSED     — normal operation, every call goes through
    OPEN       — provider is presumed down; calls are skipped without a
                 network round-trip until the cooldown elapses
    HALF_OPEN  — cooldown elapsed; exactly one trial call is allowed
                 through to test recovery before deciding CLOSED or OPEN
"""

from __future__ import annotations

import threading
import time
from typing import Dict

from backend import config

_lock = threading.Lock()
_failure_counts: Dict[str, int] = {}
_state: Dict[str, str] = {}          # provider -> CLOSED | OPEN | HALF_OPEN
_opened_at: Dict[str, float] = {}

FAILURE_THRESHOLD = config.CIRCUIT_BREAKER_FAILURE_THRESHOLD
COOLDOWN_SECONDS = config.CIRCUIT_BREAKER_COOLDOWN_SECONDS


def _get_state(provider: str) -> str:
    return _state.get(provider, "CLOSED")


def allow_request(provider: str) -> bool:
    """True if a call to this provider should actually be attempted."""
    with _lock:
        state = _get_state(provider)
        if state == "CLOSED":
            return True
        if state == "OPEN":
            if time.time() - _opened_at.get(provider, 0) >= COOLDOWN_SECONDS:
                _state[provider] = "HALF_OPEN"
                return True  # the one trial call
            return False
        if state == "HALF_OPEN":
            # A trial call is already in flight conceptually; further
            # concurrent requests during that window are also allowed
            # through in this simple implementation (no separate
            # "trial in progress" lock) — a stricter single-flight guard
            # would need per-provider request coordination this app's
            # architecture doesn't otherwise have. Documented trade-off,
            # not an oversight.
            return True
    return True


def record_success(provider: str) -> None:
    with _lock:
        _failure_counts[provider] = 0
        _state[provider] = "CLOSED"


def record_provider_failure(provider: str) -> None:
    """Call ONLY for provider-health failures (provider_unavailable,
    network_error) — see module docstring for why this is scoped
    narrowly."""
    with _lock:
        count = _failure_counts.get(provider, 0) + 1
        _failure_counts[provider] = count
        if _get_state(provider) == "HALF_OPEN" or count >= FAILURE_THRESHOLD:
            _state[provider] = "OPEN"
            _opened_at[provider] = time.time()


def get_status() -> Dict[str, dict]:
    """For observability/health endpoints."""
    with _lock:
        return {
            p: {"state": _get_state(p), "consecutive_failures": _failure_counts.get(p, 0)}
            for p in set(_state) | set(_failure_counts)
        }


def reset() -> None:
    """Test-only."""
    with _lock:
        _failure_counts.clear()
        _state.clear()
        _opened_at.clear()
