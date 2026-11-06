# Enterprise Backup & Disaster Recovery Guide

## 1. Overview
The platform features an automated, zero-data-loss snapshot backup and disaster recovery subsystem (`backend/backup_manager.py` and `scripts/run_scheduled_backup.py`).

Every snapshot archive captures:
- **Lexical Index**: SQLite FTS5 database (`storage/lexical_index.sqlite3`) with WAL checkpoint flushes.
- **Vector Store**: ChromaDB SQLite database and vector embeddings (`storage/chroma/`).
- **Access Control & Metadata**: Users (`users.json`), Collections (`collections.json`), Audit Logs (`audit_log.jsonl`), and encryption keys (`secret.key`).
- **Session History**: All past user conversations (`storage/sessions/*.json`).
- **Raw Corporate Documents**: Original source files (`data/`).
- **Integrity Manifest**: A cryptographically verifiable JSON manifest with timestamp, component checksums, and entry counts.

---

## 2. Automated Scheduled Backups
- **Linux Timer**: `deploy/systemd/multimodal-rag-backup.timer` triggers daily at `02:00:00 UTC`.
- **Retention Policy**: Controlled via `BACKUP_RETENTION_DAYS` (default: 7 days). Expired backups exceeding retention are automatically pruned after new snapshot verification succeeds.
- **Manual Trigger**:
  ```powershell
  python scripts/run_scheduled_backup.py
  ```

---

## 3. Disaster Recovery Restoration Drill

### Verification Before Restore
Every backup ZIP is verified via `zipfile.testzip()` to guarantee zero bit rot or CRC32 corruption:
```python
from backend.backup_manager import verify_backup
info = verify_backup("backups/snapshot_YYYYMMDD_HHMMSS.zip")
print(f"Archive Valid: {info['is_valid']}, Entries: {info['total_files']}")
```

### Full System Recovery Procedure
1. **Stop Application Services**:
   ```powershell
   .\scripts\stop-production.ps1
   # or on Linux: sudo systemctl stop multimodal-rag.service
   ```
2. **Execute Restore**:
   ```python
   from pathlib import Path
   from backend.backup_manager import restore_backup

   restore_backup(
       archive_path=Path("backups/snapshot_20261106_120000.zip"),
       target_data_dir=Path("data"),
       target_store_dir=Path("storage"),
   )
   ```
3. **Run Integrity Check on SQLite FTS5**:
   ```powershell
   sqlite3 storage/lexical_index.sqlite3 "PRAGMA integrity_check;"
   ```
   Must return `ok`.
4. **Restart Services**:
   ```powershell
   .\scripts\start-production.ps1
   # or on Linux: sudo systemctl start multimodal-rag.service
   ```
5. **Verify Retrieval Readiness**:
   ```powershell
   curl http://localhost:8000/health/ready
   ```
