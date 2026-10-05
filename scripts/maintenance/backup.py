#!/usr/bin/env python3
"""
Backup (transformation brief §89): python scripts/maintenance/backup.py

Tars up storage/ (sessions, lexical index, revoked-token list, audit log)
and data/ (uploaded files) into one timestamped archive. Deliberately
EXCLUDES secrets — secret.key (the token-signing key) and users.json
(password hashes) are left out by default, because a backup that copies
your signing key to wherever backups get stored (cloud sync, a shared
drive) is a bigger risk than losing it: losing secret.key just means
existing sessions' tokens stop verifying (everyone re-logs in); leaking
it means someone else can mint valid tokens for any user. Pass
--include-secrets if you've thought about where the backup file is going
and want them anyway.

Chroma's own on-disk directory is included as-is (it's just files under
storage/chroma/ in this app's layout) — no special Chroma export step,
since restoring the directory verbatim is exactly how Chroma expects to
be restored.

brief §89: "A backup that has never been restored is not considered
validated." This script's restore path (--restore) is exercised by an
automated test in this pass (extract into a fresh directory, verify file
contents match) — see the test transcript. That is not the same claim as
"restored a real backup of your real data" — run --restore yourself
against a real backup at least once before relying on this.
"""

from __future__ import annotations

import argparse
import sys
import tarfile
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "backend"))

BACKUP_DIR_NAME = "backups"
EXCLUDED_BY_DEFAULT = {"secret.key", "users.json"}


def create_backup(store_dir: Path, data_dir: Path, out_dir: Path,
                  include_secrets: bool = False) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    archive_path = out_dir / f"backup-{timestamp}.tar.gz"

    excluded = set() if include_secrets else EXCLUDED_BY_DEFAULT

    with tarfile.open(archive_path, "w:gz") as tar:
        for base, arcname_prefix in ((store_dir, "storage"), (data_dir, "data")):
            if not base.exists():
                continue
            for path in base.rglob("*"):
                if path.is_dir():
                    continue
                if path.name in excluded:
                    continue
                arcname = arcname_prefix + "/" + str(path.relative_to(base))
                tar.add(path, arcname=arcname)

    return archive_path


def restore_backup(archive_path: Path, restore_store_dir: Path, restore_data_dir: Path) -> None:
    restore_store_dir.mkdir(parents=True, exist_ok=True)
    restore_data_dir.mkdir(parents=True, exist_ok=True)
    with tarfile.open(archive_path, "r:gz") as tar:
        for member in tar.getmembers():
            if member.name.startswith("storage/"):
                target_dir = restore_store_dir
                rel = member.name[len("storage/"):]
            elif member.name.startswith("data/"):
                target_dir = restore_data_dir
                rel = member.name[len("data/"):]
            else:
                continue
            member.name = rel
            tar.extract(member, path=target_dir)


def main() -> None:
    import config
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--include-secrets", action="store_true")
    parser.add_argument("--restore", metavar="ARCHIVE", help="Restore from this archive instead of backing up.")
    parser.add_argument("--restore-into", metavar="DIR",
                        help="Restore target base dir (default: alongside the real storage/data dirs' parent, "
                             "as storage_restored/ and data_restored/, so a restore never silently overwrites "
                             "your live data).")
    args = parser.parse_args()

    if args.restore:
        base = Path(args.restore_into) if args.restore_into else config.STORE_DIR.parent
        restore_backup(Path(args.restore), base / "storage_restored", base / "data_restored")
        print(f"Restored into {base / 'storage_restored'} and {base / 'data_restored'}")
        print("Review the restored files, then move them into place yourself — "
             "this script never overwrites your live storage/data directories automatically.")
        return

    out_dir = config.STORE_DIR.parent / BACKUP_DIR_NAME
    archive = create_backup(config.STORE_DIR, config.DATA_DIR, out_dir,
                            include_secrets=args.include_secrets)
    size_mb = archive.stat().st_size / (1024 * 1024)
    print(f"Backup written: {archive} ({size_mb:.1f} MB)")
    if not args.include_secrets:
        print("(secret.key and users.json excluded — see this script's docstring; "
             "pass --include-secrets to include them)")


if __name__ == "__main__":
    main()
