"""
Phase 8 Disaster Recovery Drill and Snapshot Integrity Verification Test.
Executes an end-to-end disaster recovery scenario:
1. Provisions sample enterprise storage (SQLite FTS5, metadata, raw documents).
2. Executes create_backup() snapshot creation.
3. Validates archive structure, manifest, and CRC32 checksums via verify_backup().
4. Restores snapshot into an isolated recovery environment via restore_backup().
5. Executes SQLite PRAGMA integrity_check on the restored database.
6. Validates document contents and executes a full-text search query on the restored index.
"""

import json
import sqlite3
from pathlib import Path
import pytest
from backend import backup_manager


def test_disaster_recovery_drill(tmp_path: Path):
    source_dir = tmp_path / "source"
    source_data = source_dir / "data"
    source_store = source_dir / "storage"
    source_data.mkdir(parents=True)
    source_store.mkdir(parents=True)

    # 1. Populate enterprise state
    # SQLite Lexical Index
    sqlite_path = source_store / "lexical_index.sqlite3"
    con = sqlite3.connect(str(sqlite_path))
    cur = con.cursor()
    cur.execute("CREATE VIRTUAL TABLE documents_fts USING fts5(chunk_id, filename, content);")
    cur.execute(
        "INSERT INTO documents_fts (chunk_id, filename, content) VALUES (?, ?, ?);",
        ("chk_001", "dr_policy.txt", "Disaster recovery drill verified successfully for Phase 8 release."),
    )
    con.commit()
    con.close()

    # Metadata files
    users_data = {"usr_1": {"email": "dr_officer@corp.local", "role": "admin", "status": "active"}}
    (source_store / "users.json").write_text(json.dumps(users_data), encoding="utf-8")

    cols_data = {"col_1": {"name": "Disaster Recovery", "files": ["dr_policy.txt"]}}
    (source_store / "collections.json").write_text(json.dumps(cols_data), encoding="utf-8")

    (source_store / "audit_log.jsonl").write_text('{"action": "test_dr_init"}\n', encoding="utf-8")
    (source_store / "secret.key").write_bytes(b"DUMMY_SECRET_KEY_FOR_DR_DRILL_0123456789=")

    # Raw documents
    doc_path = source_data / "dr_policy.txt"
    doc_content = "Disaster recovery drill verified successfully for Phase 8 release."
    doc_path.write_text(doc_content, encoding="utf-8")

    # 2. Execute snapshot creation
    backup_zip = tmp_path / "backups" / "dr_snapshot.zip"
    result = backup_manager.create_backup(backup_zip, data_dir=source_data, store_dir=source_store)

    assert result["status"] == "success"
    assert backup_zip.exists()
    assert backup_zip.stat().st_size > 0
    assert result["manifest"]["components"]["lexical_index"] is True
    assert result["manifest"]["components"]["raw_documents"] == 1

    # 3. Verify archive and CRC32 checksums
    verification = backup_manager.verify_backup(backup_zip)
    assert verification["is_valid"] is True
    assert "manifest.json" in verification["files"]
    assert "storage/lexical_index.sqlite3" in verification["files"]
    assert "data/dr_policy.txt" in verification["files"]

    # 4. Restore into an isolated clean environment
    restore_target = tmp_path / "recovered_environment"
    recovered_data = restore_target / "data"
    recovered_store = restore_target / "storage"

    restore_res = backup_manager.restore_backup(
        backup_zip,
        target_data_dir=recovered_data,
        target_store_dir=recovered_store,
    )
    assert restore_res["status"] == "restored"

    # 5. Verify restored database integrity
    recovered_sqlite = recovered_store / "lexical_index.sqlite3"
    assert recovered_sqlite.exists()

    rec_con = sqlite3.connect(str(recovered_sqlite))
    rec_cur = rec_con.cursor()
    integrity_rows = rec_cur.execute("PRAGMA integrity_check;").fetchall()
    assert integrity_rows == [("ok",)], f"Integrity check failed: {integrity_rows}"

    # 6. Execute retrieval query on restored index
    search_results = rec_cur.execute(
        "SELECT chunk_id, filename, content FROM documents_fts WHERE documents_fts MATCH 'Disaster';"
    ).fetchall()
    assert len(search_results) == 1
    assert search_results[0][0] == "chk_001"
    assert search_results[0][1] == "dr_policy.txt"
    rec_con.close()

    # 7. Verify restored raw files and user metadata
    recovered_doc = (recovered_data / "dr_policy.txt").read_text(encoding="utf-8")
    assert recovered_doc == doc_content

    recovered_users = json.loads((recovered_store / "users.json").read_text(encoding="utf-8"))
    assert "usr_1" in recovered_users
    assert recovered_users["usr_1"]["email"] == "dr_officer@corp.local"
