"""
Phase 3D — Asynchronous ingestion queue.

The existing synchronous /api/ingest blocks the request until every file is
parsed + embedded, which is slow for big PDFs / audio. This module adds an
OPT-IN background path used only by the new /api/ingest/async endpoint:

  1. The endpoint saves the uploads to disk (fast) and enqueues one job.
  2. A small in-process ThreadPoolExecutor (config.INGEST_ASYNC_WORKERS)
     runs the SAME ingest_mod.ingest_file() the sync path uses — nothing in
     ingestion or retrieval is modified.
  3. The client polls /api/ingest/status/{job_id} for progress + results.

Everything is in-process (no Redis/Celery) so it stays fully offline and adds
no new hard dependency. The synchronous /api/ingest endpoint is untouched.
"""

from __future__ import annotations

import json
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from backend import config
from backend.ingestion import ingest as ingest_mod

# One shared worker pool for the whole process.
_executor = ThreadPoolExecutor(max_workers=max(1, config.INGEST_ASYNC_WORKERS))

# job_id -> job state. Guarded by _lock (worker threads mutate it).
_jobs: Dict[str, Dict[str, Any]] = {}
_lock = threading.Lock()
_JOBS_FILE = Path(getattr(config, "STORE_DIR", getattr(config, "STORAGE_DIR", Path("storage")))) / "ingestion_jobs.json"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _save_jobs_to_disk() -> None:
    try:
        _JOBS_FILE.parent.mkdir(parents=True, exist_ok=True)
        temp_file = _JOBS_FILE.with_suffix(".tmp")
        with open(temp_file, "w", encoding="utf-8") as f:
            json.dump(_jobs, f, indent=2)
        temp_file.replace(_JOBS_FILE)
    except Exception as exc:
        pass


def _load_jobs_from_disk() -> None:
    if not _JOBS_FILE.exists():
        return
    try:
        with open(_JOBS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            if isinstance(data, dict):
                for jid, job in data.items():
                    if job.get("status") in ("queued", "running"):
                        job["status"] = "interrupted"
                        job["error"] = "Process restarted while job was in-flight"
                        job["updated_at"] = _now()
                    _jobs[jid] = job
    except Exception:
        pass


_load_jobs_from_disk()


def _set(job_id: str, **fields: Any) -> None:
    with _lock:
        job = _jobs.get(job_id)
        if job is not None:
            job.update(fields)
            _save_jobs_to_disk()


def submit(
    paths: List[str],
    session_id: str,
    user_id: str,
    on_complete: Optional[Callable[..., None]] = None,
    mode: str = "max_quality",
    org_id: Optional[str] = None,
) -> str:
    """Enqueue a background ingest of already-saved *paths*.

    Returns a job_id immediately. `on_complete(session_id, user_id, org_id)` (if given)
    runs after all files finish, on the worker thread — used to refresh the
    session file list + invalidate caches, mirroring the sync endpoint.
    `mode` (brief §44) is passed straight through to ingest_file() for
    every file in this job.
    """
    job_id = uuid.uuid4().hex
    org_id_val = org_id or "default_org"
    with _lock:
        _jobs[job_id] = {
            "job_id": job_id,
            "session_id": session_id,
            "user_id": user_id,
            "org_id": org_id_val,
            "status": "queued",           # queued | running | done | error
            "total": len(paths),
            "completed": 0,
            "results": [],
            "created_at": _now(),
            "updated_at": _now(),
            "error": None,
        }
        _save_jobs_to_disk()
    _executor.submit(_run, job_id, paths, session_id, user_id, org_id_val, on_complete, mode)
    return job_id


def _run(job_id: str, paths: List[str], session_id: str, user_id: str, org_id: str,
         on_complete: Optional[Callable[..., None]], mode: str = "max_quality") -> None:
    _set(job_id, status="running", updated_at=_now())
    results: List[Dict[str, Any]] = []
    for path in paths:
        try:
            res = ingest_mod.ingest_file(
                path, session_id=session_id, user_id=user_id, mode=mode, org_id=org_id)
        except Exception as exc:                       # per-file isolation
            res = {"file": path, "error": str(exc)}
        results.append(res)
        with _lock:
            job = _jobs.get(job_id)
            if job is not None:
                job["completed"] += 1
                job["results"] = list(results)
                job["updated_at"] = _now()
                _save_jobs_to_disk()

    try:
        if on_complete is not None:
            import inspect
            sig = inspect.signature(on_complete)
            if len(sig.parameters) >= 3:
                on_complete(session_id, user_id, org_id)
            else:
                on_complete(session_id, user_id)
        _set(job_id, status="done", updated_at=_now())
    except Exception as exc:
        _set(job_id, status="error", error=str(exc), updated_at=_now())


def status(job_id: str) -> Optional[Dict[str, Any]]:
    """Return a snapshot copy of the job state, or None if unknown."""
    with _lock:
        job = _jobs.get(job_id)
        return dict(job) if job is not None else None
