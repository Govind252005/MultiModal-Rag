"""
Enterprise Structured Audit Logging System.

Records security and administrative lifecycle events:
- Document uploads and deletions
- Document reprocessing
- Collection creation, modification, and deletion
- Model selection and configuration changes
- User role and status updates
- Authentication and security lockout events
"""

from __future__ import annotations

import datetime as _dt
import json
import os
import threading
from pathlib import Path
from typing import Any, Dict, List, Optional

from backend import config

_audit_lock = threading.RLock()


def _audit_file() -> Path:
    return config.STORE_DIR / "audit_log.jsonl"


def _now() -> str:
    return _dt.datetime.now().isoformat(timespec="seconds")


def record_audit(
    action: str,
    user_id: str,
    email: str = "",
    org_id: str = "default_org",
    resource: str = "",
    outcome: str = "success",
    details: Optional[Dict[str, Any]] = None,
    ip_address: Optional[str] = None,
) -> Dict[str, Any]:
    """Append a structured audit log entry safely."""
    event = {
        "timestamp": _now(),
        "action": action,
        "user_id": user_id,
        "email": email,
        "org_id": org_id or "default_org",
        "resource": resource,
        "outcome": outcome,
        "ip_address": ip_address or "127.0.0.1",
        "details": details or {},
    }

    line = json.dumps(event, ensure_ascii=False) + "\n"

    with _audit_lock:
        path = _audit_file()
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "a", encoding="utf-8") as f:
            f.write(line)
            f.flush()

    return event


def query_audit_logs(
    org_id: Optional[str] = None,
    action: Optional[str] = None,
    user_email: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
) -> Dict[str, Any]:
    """Query audit logs in reverse chronological order with filtering and pagination."""
    path = _audit_file()
    if not path.exists():
        return {"total": 0, "events": []}

    target_org = (org_id or "").strip().lower()
    act_filter = (action or "").strip().lower()
    email_filter = (user_email or "").strip().lower()

    matched: List[Dict[str, Any]] = []

    with _audit_lock:
        try:
            with open(path, "r", encoding="utf-8") as f:
                lines = f.readlines()
        except Exception:
            return {"total": 0, "events": []}

    # Process in reverse (most recent first)
    for line in reversed(lines):
        line = line.strip()
        if not line:
            continue
        try:
            item = json.loads(line)
        except Exception:
            continue

        if target_org and (item.get("org_id") or "default_org").strip().lower() != target_org:
            continue
        if act_filter and act_filter != "all" and item.get("action", "").lower() != act_filter:
            continue
        if email_filter and email_filter not in item.get("email", "").lower():
            continue

        matched.append(item)

    total = len(matched)
    paginated = matched[offset : offset + limit]

    return {
        "total": total,
        "events": paginated,
        "limit": limit,
        "offset": offset,
    }
