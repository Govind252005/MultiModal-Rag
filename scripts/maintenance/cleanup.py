#!/usr/bin/env python3
"""
Data retention cleanup (transformation brief §88): see docs/data-retention.md.

    python scripts/maintenance/cleanup.py --dry-run
    python scripts/maintenance/cleanup.py

Never run automatically (no cron/startup hook anywhere in this codebase)
— see docs/data-retention.md for why. Everything this script *would*
delete is listed in --dry-run mode before anything is touched for real.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
from pathlib import Path
from typing import Iterable, List, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "backend"))


def _age_days(mtime: float, now: dt.datetime) -> float:
    modified = dt.datetime.fromtimestamp(mtime)
    return (now - modified).total_seconds() / 86400.0


def find_old_sessions(sessions_dir: Path, retention_days: int,
                      now: dt.datetime) -> List[Path]:
    """Sessions whose *last-modified* time is older than retention_days.
    retention_days <= 0 means "never auto-delete" (the safe default) —
    returns an empty list rather than treating 0 as "everything is
    infinitely old."""
    if retention_days <= 0 or not sessions_dir.exists():
        return []
    return [
        p for p in sessions_dir.glob("*.json")
        if _age_days(p.stat().st_mtime, now) > retention_days
    ]


def find_old_eval_reports(reports_dir: Path, retention_days: int,
                          now: dt.datetime) -> List[Path]:
    if retention_days <= 0 or not reports_dir.exists():
        return []
    return [
        p for p in reports_dir.iterdir()
        if p.is_dir() and _age_days(p.stat().st_mtime, now) > retention_days
    ]


def session_owner_and_data_dir(session_path: Path, data_dir: Path) -> Path:
    """The uploaded-files directory for a session, by the same
    character-allowlist sanitization main.py uses (brief §88: cleaning up
    a session's index/messages without also cleaning up its uploaded
    files would leave orphaned data behind)."""
    session_id = session_path.stem
    safe = "".join(c for c in session_id if c.isalnum() or c in "-_")
    return data_dir / safe


def plan(config, now: dt.datetime) -> dict:
    """Compute what WOULD be deleted, without deleting anything. Pure
    function of (config, now) — this is what --dry-run prints and what
    the real run executes, so the two paths can never drift apart."""
    old_sessions = find_old_sessions(
        config.SESSIONS_DIR, getattr(config, "SESSION_RETENTION_DAYS", 0), now)
    old_reports = find_old_eval_reports(
        Path(__file__).resolve().parents[2] / "reports" / "evaluation",
        getattr(config, "EVAL_REPORT_RETENTION_DAYS", 0), now)
    return {
        "sessions_to_delete": old_sessions,
        "session_data_dirs_to_delete": [
            session_owner_and_data_dir(p, config.DATA_DIR) for p in old_sessions
        ],
        "eval_reports_to_delete": old_reports,
    }


def execute(plan_result: dict, dry_run: bool) -> Tuple[int, int]:
    """Returns (files_removed, dirs_removed). In dry-run mode, removes
    nothing and returns the counts of what WOULD have been removed."""
    import shutil
    files_removed = dirs_removed = 0
    for p in plan_result["sessions_to_delete"]:
        if not dry_run:
            p.unlink(missing_ok=True)
        files_removed += 1
    for d in plan_result["session_data_dirs_to_delete"]:
        if d.exists():
            if not dry_run:
                shutil.rmtree(d, ignore_errors=True)
            dirs_removed += 1
    for d in plan_result["eval_reports_to_delete"]:
        if not dry_run:
            shutil.rmtree(d, ignore_errors=True)
        dirs_removed += 1
    return files_removed, dirs_removed


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true",
                        help="List what would be deleted; delete nothing.")
    args = parser.parse_args()

    import config
    now = dt.datetime.now()
    result = plan(config, now)

    print("=" * 60)
    print(("DRY RUN — " if args.dry_run else "") + "DATA RETENTION CLEANUP")
    print("=" * 60)
    print(f"Session retention: {getattr(config, 'SESSION_RETENTION_DAYS', 0)} days "
         f"(0 = never auto-delete)")
    print(f"Eval report retention: {getattr(config, 'EVAL_REPORT_RETENTION_DAYS', 0)} days")
    print()
    print(f"Sessions past retention: {len(result['sessions_to_delete'])}")
    for p in result["sessions_to_delete"]:
        print(f"  - {p}")
    print(f"Eval reports past retention: {len(result['eval_reports_to_delete'])}")
    for p in result["eval_reports_to_delete"]:
        print(f"  - {p}")

    files_removed, dirs_removed = execute(result, dry_run=args.dry_run)
    print()
    if args.dry_run:
        print(f"Would remove {files_removed} session file(s), {dirs_removed} directory(ies). "
             f"Re-run without --dry-run to actually delete.")
    else:
        print(f"Removed {files_removed} session file(s), {dirs_removed} directory(ies).")
    print("=" * 60)


if __name__ == "__main__":
    main()
