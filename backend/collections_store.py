"""
Enterprise Collections Store (Thread-safe, process-safe, tenant-isolated).

Provides logical grouping of documents into Collections to control retrieval scope,
enforce organization boundaries, and organize multi-format enterprise assets.
"""

from __future__ import annotations

import datetime as _dt
import json
import os
import threading
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

from backend import config
from backend.auth import atomic_write_json, file_lock

_col_lock = threading.RLock()


def _col_path() -> Path:
    return config.STORE_DIR / "collections.json"


def _now() -> str:
    return _dt.datetime.now().isoformat(timespec="seconds")


def _load_all() -> Dict[str, Dict[str, Any]]:
    p = _col_path()
    if not p.exists():
        return {}
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _save_all(data: Dict[str, Dict[str, Any]]) -> None:
    atomic_write_json(_col_path(), data)


def _mutate(mutator_fn):
    with _col_lock:
        with file_lock(_col_path()):
            all_cols = _load_all()
            result = mutator_fn(all_cols)
            _save_all(all_cols)
            return result


def list_collections(
    owner_id: Optional[str] = None,
    org_id: Optional[str] = None,
    role: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """List collections. Admins see all org collections; users see own or org collections."""
    with _col_lock:
        all_cols = _load_all()

    target_org = (org_id or "default_org").strip().lower()
    out: List[Dict[str, Any]] = []

    for c in all_cols.values():
        c_org = (c.get("org_id") or "default_org").strip().lower()
        if c_org != target_org:
            continue
        # If user is not admin, they only see their own collections or shared org collections
        if role != "admin" and owner_id and c.get("owner_id") != owner_id and not c.get("is_shared", True):
            continue

        out.append({
            "id": c["id"],
            "name": c.get("name", "Untitled Collection"),
            "description": c.get("description", ""),
            "owner_id": c.get("owner_id", ""),
            "org_id": c.get("org_id", target_org),
            "created_at": c.get("created_at", _now()),
            "updated_at": c.get("updated_at", _now()),
            "document_count": len(c.get("files", [])),
            "files": c.get("files", []),
            "is_shared": c.get("is_shared", True),
        })

    return sorted(out, key=lambda x: x.get("updated_at", ""), reverse=True)


def get_collection(col_id: str, org_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
    with _col_lock:
        c = _load_all().get(col_id)
    if not c:
        return None
    if org_id and (c.get("org_id") or "default_org").strip().lower() != org_id.strip().lower():
        return None
    return c


def create_collection(
    name: str,
    description: str = "",
    owner_id: str = "default_user",
    org_id: str = "default_org",
    files: Optional[List[str]] = None,
    is_shared: bool = True,
) -> Dict[str, Any]:
    name = (name or "").strip()
    if not name:
        raise ValueError("Collection name cannot be empty.")

    col_id = f"col_{uuid.uuid4().hex[:10]}"
    target_org = (org_id or "default_org").strip().lower()
    now_ts = _now()

    new_col = {
        "id": col_id,
        "name": name,
        "description": (description or "").strip(),
        "owner_id": owner_id,
        "org_id": target_org,
        "created_at": now_ts,
        "updated_at": now_ts,
        "files": sorted(list(set(files or []))),
        "is_shared": is_shared,
    }

    def _apply(cols: Dict[str, Any]):
        cols[col_id] = new_col
        return new_col

    return _mutate(_apply)


def update_collection(
    col_id: str,
    name: Optional[str] = None,
    description: Optional[str] = None,
    org_id: Optional[str] = None,
    owner_id: Optional[str] = None,
    role: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    def _apply(cols: Dict[str, Any]):
        c = cols.get(col_id)
        if not c:
            return None
        if org_id and (c.get("org_id") or "default_org").strip().lower() != org_id.strip().lower():
            raise PermissionError("Access denied: collection belongs to a different organization.")
        if role != "admin" and owner_id and c.get("owner_id") and c.get("owner_id") != owner_id:
            raise PermissionError("Access denied: collection belongs to another user.")

        if name is not None and name.strip():
            c["name"] = name.strip()
        if description is not None:
            c["description"] = description.strip()
        c["updated_at"] = _now()
        return c

    return _mutate(_apply)


def delete_collection(
    col_id: str,
    org_id: Optional[str] = None,
    owner_id: Optional[str] = None,
    role: Optional[str] = None,
) -> bool:
    def _apply(cols: Dict[str, Any]):
        c = cols.get(col_id)
        if not c:
            return False
        if org_id and (c.get("org_id") or "default_org").strip().lower() != org_id.strip().lower():
            raise PermissionError("Access denied: collection belongs to a different organization.")
        if role != "admin" and owner_id and c.get("owner_id") and c.get("owner_id") != owner_id:
            raise PermissionError("Access denied: collection belongs to another user.")
        del cols[col_id]
        return True

    return _mutate(_apply)


def add_file_to_collection(col_id: str, filename: str, org_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
    clean_name = Path(filename).name

    def _apply(cols: Dict[str, Any]):
        c = cols.get(col_id)
        if not c:
            return None
        if org_id and (c.get("org_id") or "default_org").strip().lower() != org_id.strip().lower():
            raise PermissionError("Access denied.")
        current_files = set(c.get("files", []))
        current_files.add(clean_name)
        c["files"] = sorted(list(current_files))
        c["updated_at"] = _now()
        return c

    return _mutate(_apply)


def remove_file_from_collection(col_id: str, filename: str, org_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
    clean_name = Path(filename).name

    def _apply(cols: Dict[str, Any]):
        c = cols.get(col_id)
        if not c:
            return None
        if org_id and (c.get("org_id") or "default_org").strip().lower() != org_id.strip().lower():
            raise PermissionError("Access denied.")
        current_files = set(c.get("files", []))
        current_files.discard(clean_name)
        c["files"] = sorted(list(current_files))
        c["updated_at"] = _now()
        return c

    return _mutate(_apply)


def get_collection_files(col_id: str, org_id: Optional[str] = None) -> List[str]:
    c = get_collection(col_id, org_id=org_id)
    return c.get("files", []) if c else []
