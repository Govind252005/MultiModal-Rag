"""
Explicit, backend-authoritative "active generation provider" state per user
(transformation-brief §51A.9-§51A.13).

Why this exists: before this file, provider selection was purely a
per-request parameter (`QueryRequest.provider`) defaulting to
`config.DEFAULT_PROVIDER` — there was no persisted notion of "the provider
this user is currently using", so the frontend had nothing authoritative to
read back (§51A.11) and every request that omitted `provider` silently used
Ollama even if the user had just switched to a validated cloud provider.

Rules enforced here (straight from the brief):
  - Startup default is always Ollama/local (§51A.1) — a stored active
    provider is only ever set by an explicit activation call.
  - Activating a cloud provider requires a previously-stored, working API
    key for that provider (§51A.4/§51A.6) — validation and activation are
    two separate steps, and this module refuses to skip that check.
  - Never stores or returns the API key itself (§51A.15) — only the
    provider name and model.
"""

from __future__ import annotations

import json
import threading
from pathlib import Path
from typing import Any, Dict, Optional

from backend import config

_lock = threading.Lock()


def _path() -> Path:
    return config.STORE_DIR / "active_provider.json"


def _load() -> Dict[str, Any]:
    p = _path()
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _save(data: Dict[str, Any]) -> None:
    _path().write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def get_active(user_id: str) -> str:
    """Returns the provider name. Falls back to config.DEFAULT_PROVIDER
    (Ollama, per §51A.1) if the user has never explicitly activated one."""
    with _lock:
        data = _load()
    entry = data.get(user_id)
    if entry and entry.get("provider"):
        return entry["provider"]
    return config.DEFAULT_PROVIDER


def get_active_model(user_id: str) -> Optional[str]:
    """Returns the custom model name if selected, else None."""
    with _lock:
        data = _load()
    entry = data.get(user_id)
    if entry and entry.get("model"):
        return entry["model"]
    return None


def get_active_full(user_id: str) -> Dict[str, Any]:
    provider = get_active(user_id)
    is_local = provider == "ollama"
    custom_model = get_active_model(user_id)
    model = (config.LLM_MODEL if is_local else (custom_model or _model_for(provider)))
    return {
        "provider": provider,
        "model": model,
        "mode": "local" if is_local else "cloud",
        "status": "active",
    }


def _model_for(provider: str) -> str:
    return {
        "gemini": config.GEMINI_MODEL,
        "openai": config.OPENAI_MODEL,
        "claude": config.CLAUDE_MODEL,
        "groq": config.GROQ_MODEL,
    }.get(provider, "")


def set_active(user_id: str, provider: str, model: Optional[str] = None) -> Dict[str, Any]:
    """Persist the explicit activation (§51A.6/§51A.7) with optional model override. Caller is
    responsible for having already checked the provider is allowed and, for
    a cloud provider, that a validated key exists — this module only
    records the decision, it doesn't re-derive authorization."""
    with _lock:
        data = _load()
        entry: Dict[str, Any] = {"provider": provider}
        if model:
            entry["model"] = model.strip()
        data[user_id] = entry
        _save(data)
    return get_active_full(user_id)

