"""
Provider error classification.

AUDIT_REPORT.md P0-5 / transformation brief §52 & §51A.21: the previous
router caught *any* exception from a cloud provider and, if
PROVIDER_FAILOVER_TO_LOCAL was set (the default), silently generated the
answer with local Ollama instead — including on an invalid API key or a
malformed request, which should fail immediately and visibly rather than
quietly substituting a different model's answer for what the user explicitly
asked for.

This module gives the router a best-effort classification so it can apply
the brief's own example policy:

    invalid API key      -> fail immediately, no retry, no failover
    invalid request       -> fail immediately, no retry, no failover
    rate limited           -> may retry / failover
    network / timeout      -> may retry / failover (limited)
    provider unavailable   -> may failover

We don't have network access to every SDK's exact exception hierarchy in
this sandbox, so this intentionally uses duck-typing against attributes that
OpenAI's, Anthropic's, and Groq's Python SDKs all expose on their error
classes (they're all modelled on the same "APIStatusError has .status_code"
convention), plus generic fallbacks (requests/urllib3 timeouts, connection
errors) so an unknown SDK still degrades to a safe default (no failover)
rather than the previous "always failover" behaviour.
"""

from __future__ import annotations

from typing import Optional

RETRYABLE = {"rate_limited", "network_error", "provider_unavailable"}
NON_RETRYABLE = {"invalid_api_key", "invalid_request", "missing_api_key"}


def classify(exc: BaseException) -> str:
    """Return one of: invalid_api_key, missing_api_key, invalid_request,
    rate_limited, network_error, provider_unavailable, unknown."""
    # Missing/never-configured key surfaces as ValueError from
    # cloud_providers._get_key() / gemini_provider._get_key().
    if isinstance(exc, ValueError):
        return "missing_api_key"

    status = getattr(exc, "status_code", None)
    if status is None:
        resp = getattr(exc, "response", None)
        status = getattr(resp, "status_code", None)

    name = exc.__class__.__name__.lower()

    if status == 401 or "authenticationerror" in name or "permissiondenied" in name:
        return "invalid_api_key"
    if status == 429 or "ratelimit" in name:
        return "rate_limited"
    if status == 400 or "badrequest" in name or "invalidrequest" in name:
        return "invalid_request"
    if status is not None and 500 <= int(status) < 600:
        return "provider_unavailable"
    if any(k in name for k in ("timeout", "connectionerror", "apiconnectionerror")):
        return "network_error"

    return "unknown"


def is_retryable(category: str) -> bool:
    return category in RETRYABLE


def user_message(category: str, provider: str, exc: BaseException) -> str:
    messages = {
        "invalid_api_key": f"The {provider} API key was rejected (authentication failed).",
        "missing_api_key": f"No {provider} API key is configured for this account.",
        "invalid_request": f"{provider} rejected the request as invalid.",
        "rate_limited": f"{provider} is rate-limiting this account right now.",
        "network_error": f"Could not reach {provider} (network/timeout).",
        "provider_unavailable": f"{provider} is currently unavailable (server error).",
        "unknown": f"{provider} generation failed.",
    }
    return f"{messages.get(category, messages['unknown'])} ({exc})"
