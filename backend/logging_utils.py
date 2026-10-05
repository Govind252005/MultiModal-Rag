"""
Structured request logging + security audit log (transformation brief
§54/§55).

Two distinct things, kept separate on purpose:
  log_request()  — one line per HTTP request, for operational debugging.
                    Never logs passwords, API keys, tokens, or raw
                    document content (brief §54's explicit "never log"
                    list) — only IDs, sizes, and status.
  audit_log()     — one line per SECURITY-SENSITIVE event (login, logout,
                    failed login, API key added/removed, file
                    upload/delete, admin action), appended to a dedicated
                    file so it can be reviewed/retained independently of
                    general request logs.

Both are line-delimited JSON (JSONL) — trivially greppable/jq-able and
ingestible by any real log pipeline later, without pulling in a logging
framework dependency for what is currently two files' worth of output.
"""

from __future__ import annotations

import json
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from backend import config

_MAX_AUDIT_LOG_BYTES = 10 * 1024 * 1024  # 10MB — brief §55 "implement log rotation"


def new_request_id() -> str:
    return uuid.uuid4().hex[:16]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


def log_request(request_id: str, **fields: Any) -> None:
    try:
        print("[request] " + json.dumps({"request_id": request_id, "timestamp": _now(), **fields},
                                        ensure_ascii=False, default=str))
    except Exception:
        pass


def _audit_path() -> Path:
    return config.STORE_DIR / "audit.log"


def _rotate_if_needed() -> None:
    path = _audit_path()
    try:
        if path.exists() and path.stat().st_size > _MAX_AUDIT_LOG_BYTES:
            backup = config.STORE_DIR / "audit.log.1"
            backup.unlink(missing_ok=True)
            path.rename(backup)
    except Exception:
        pass


def audit_log(event: str, user_id: Optional[str] = None, **fields: Any) -> None:
    """Security-sensitive event (brief §55). NEVER pass a password, API
    key, or raw token in `fields` — callers are responsible for that;
    this function does not attempt to scrub fields after the fact,
    because a scrubber that tries to guess "does this look like a
    secret" is exactly the kind of unreliable safety net brief §112
    ("no security theater") warns against. Keep callers disciplined
    instead.
    """
    entry = {
        "timestamp": _now(), "event": event, "user_id": user_id,
        **fields,
    }
    try:
        _rotate_if_needed()
        with _audit_path().open("a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False, default=str) + "\n")
    except Exception:
        pass
    # Also emit to stdout via the same structured channel as ordinary
    # request logs, so a log aggregator that only tails stdout still sees
    # security events without needing a second file mounted.
    try:
        print("[audit] " + json.dumps(entry, ensure_ascii=False, default=str))
    except Exception:
        pass
