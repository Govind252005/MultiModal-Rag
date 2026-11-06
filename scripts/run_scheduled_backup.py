"""
Automated Scheduled Backup Runner with Retention Policy.
Creates a verified snapshot archive and rotates snapshots exceeding retention limit.
"""

import logging
import sys
import time
from pathlib import Path

# Add project root to path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from backend.backup_manager import create_backup, verify_backup
from backend import config

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] %(levelname)s %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("backup_scheduler")

import os

RETENTION_DAYS = int(os.getenv("BACKUP_RETENTION_DAYS", "7"))


def run_backup():
    backups_dir = ROOT / "backups"
    backups_dir.mkdir(parents=True, exist_ok=True)

    timestamp = time.strftime("%Y%m%d_%H%M%S")
    snapshot_path = backups_dir / f"snapshot_{timestamp}.zip"

    logger.info(f"Starting scheduled snapshot backup: {snapshot_path}")
    try:
        res = create_backup(snapshot_path)
        logger.info(f"Backup created successfully: {res['size_bytes']} bytes")

        # Verify archive
        ver = verify_backup(snapshot_path)
        logger.info(f"Integrity verified. Total archive entries: {ver['total_files']}")

        # Enforce retention policy
        existing_snapshots = sorted(backups_dir.glob("snapshot_*.zip"), key=lambda p: p.stat().st_mtime)
        if len(existing_snapshots) > RETENTION_DAYS:
            to_remove = existing_snapshots[:-RETENTION_DAYS]
            for old in to_remove:
                logger.info(f"Pruning expired backup according to {RETENTION_DAYS}-day retention: {old.name}")
                old.unlink()

        logger.info("Scheduled backup run complete.")
        return 0
    except Exception as exc:
        logger.error(f"Scheduled backup failed with exception: {exc}", exc_info=True)
        return 1


if __name__ == "__main__":
    sys.exit(run_backup())
