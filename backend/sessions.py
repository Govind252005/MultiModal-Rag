"""
Chat session store (per-user, ChatGPT/Claude-style).

Each session belongs to ONE user (owner_id) and holds its own library +
message history. One JSON file per session under storage/sessions/.
Listing is filtered by owner so users never see each other's chats.

Concurrency (brief §42): two overlapping requests against the SAME
session (e.g. two messages sent in quick succession, or a message
arriving while a rename is in flight) used to be a plain read-modify-
write with no synchronization — the second write's "modify" step could
be based on stale data read before the first write landed, silently
losing the first update. Two fixes, honestly scoped:
  1. Per-session in-process lock — correctly serializes concurrent
     writers WITHIN this one backend process, which is this app's actual
     deployment model (see docs/architecture.md: single-process
     local/desktop). This does NOT protect against two separate backend
     *processes* writing the same session file — that would need real
     file locking (`fcntl`/`msvcrt`) or a real database, out of scope
     for the single-process architecture this app targets today.
  2. Atomic write (write to a temp file, then os.replace()) — protects
     against a crash/kill mid-write leaving a truncated, corrupt JSON
     file, regardless of process count.
"""

from __future__ import annotations

import datetime as _dt
import json
import os
import threading
import uuid
from typing import Any, Dict, List, Optional

from backend import config

_locks_guard = threading.Lock()
_session_locks: Dict[str, threading.Lock] = {}


def _lock_for(session_id: str) -> threading.Lock:
    with _locks_guard:
        lock = _session_locks.get(session_id)
        if lock is None:
            lock = threading.Lock()
            _session_locks[session_id] = lock
        return lock


def _now() -> str:
    return _dt.datetime.now().isoformat(timespec="seconds")


def _path(session_id: str):
    safe = "".join(c for c in session_id if c.isalnum() or c in "-_")
    return config.SESSIONS_DIR / f"{safe}.json"


def _read(session_id: str) -> Optional[Dict[str, Any]]:
    p = _path(session_id)
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return None


def _write(session: Dict[str, Any]) -> None:
    session["updated_at"] = _now()
    path = _path(session["id"])
    # Atomic write: never leave a half-written/corrupt session file behind
    # if the process is killed mid-write.
    tmp_path = path.with_suffix(f".{uuid.uuid4().hex[:8]}.tmp")
    tmp_path.write_text(json.dumps(session, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(tmp_path, path)  # atomic on POSIX and Windows


def _read_modify_write(session_id: str, modify) -> Optional[Dict[str, Any]]:
    """Read, apply `modify(session) -> session|None`, write — all under
    this session's lock, so two concurrent callers can never interleave
    their read and write halves and silently drop one update."""
    with _lock_for(session_id):
        s = _read(session_id)
        if s is None:
            return None
        result = modify(s)
        if result is None:
            return None
        _write(result)
        return result


# ------------------------------------------------------------------ CRUD
def create_session(owner_id: str, title: str = "New chat") -> Dict[str, Any]:
    sid = uuid.uuid4().hex[:12]
    session = {
        "id": sid, "owner_id": owner_id, "title": title or "New chat",
        "created_at": _now(), "updated_at": _now(),
        "messages": [], "files": [],
    }
    _write(session)
    return session


def get_session(session_id: str) -> Optional[Dict[str, Any]]:
    return _read(session_id)


def owns(session_id: str, owner_id: str) -> bool:
    s = _read(session_id)
    return bool(s and s.get("owner_id") == owner_id)


def list_sessions(owner_id: str) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for p in config.SESSIONS_DIR.glob("*.json"):
        try:
            s = json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            continue
        if s.get("owner_id") != owner_id:
            continue
        out.append({
            "id": s.get("id"), "title": s.get("title", "New chat"),
            "created_at": s.get("created_at", ""), "updated_at": s.get("updated_at", ""),
            "message_count": len(s.get("messages", [])), "file_count": len(s.get("files", [])),
        })
    out.sort(key=lambda x: x.get("updated_at", ""), reverse=True)
    return out


def delete_session(session_id: str) -> bool:
    p = _path(session_id)
    if p.exists():
        p.unlink()
        return True
    return False


def rename_session(session_id: str, title: str) -> Optional[Dict[str, Any]]:
    def modify(s: Dict[str, Any]) -> Dict[str, Any]:
        s["title"] = title.strip() or s["title"]
        return s
    return _read_modify_write(session_id, modify)


# ------------------------------------------------------------------ mutations
def append_message(session_id: str, message: Dict[str, Any]) -> None:
    def modify(s: Dict[str, Any]) -> Dict[str, Any]:
        msg = {**message, "ts": _now()}
        s["messages"].append(msg)
        if s["title"] in ("New chat", "") and msg.get("role") == "user":
            text = (msg.get("text") or "").strip().replace("\n", " ")
            if text:
                s["title"] = text[:48] + ("…" if len(text) > 48 else "")
        return s
    _read_modify_write(session_id, modify)


def set_files(session_id: str, files: List[Dict[str, Any]]) -> None:
    def modify(s: Dict[str, Any]) -> Dict[str, Any]:
        s["files"] = files
        return s
    _read_modify_write(session_id, modify)


def ensure_exists(session_id: str, owner_id: str) -> Dict[str, Any]:
    s = _read(session_id)
    if s:
        return s
    sid = "".join(c for c in session_id if c.isalnum() or c in "-_") or uuid.uuid4().hex[:12]
    session = {
        "id": sid, "owner_id": owner_id, "title": "New chat",
        "created_at": _now(), "updated_at": _now(), "messages": [], "files": [],
    }
    _write(session)
    return session
