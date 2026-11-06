"""
Unit test for Enterprise Backup & Recovery Manager.
Verifies snapshot creation, manifest validation, zip archive integrity,
and complete round-trip restoration of documents and storage state.
"""

import json
from pathlib import Path
from backend.backup_manager import create_backup, verify_backup, restore_backup


def test_backup_create_verify_and_restore(tmp_path: Path):
    src_data = tmp_path / "data"
    src_store = tmp_path / "store"
    src_data.mkdir()
    src_store.mkdir()

    # Create mock state
    doc1 = src_data / "sample.pdf"
    doc1.write_bytes(b"%PDF-1.4 mock content")

    doc2 = src_data / "notes.txt"
    doc2.write_text("Confidential enterprise notes", encoding="utf-8")

    users_file = src_store / "users.json"
    users_file.write_text(json.dumps([{"id": "usr_1", "email": "admin@enterprise.local"}]), encoding="utf-8")

    sqlite_file = src_store / "lexical_index.sqlite3"
    sqlite_file.write_bytes(b"SQLite format 3\x00mockdb")

    backup_zip = tmp_path / "backup_archive.zip"

    # 1. Create backup
    res = create_backup(
        output_path=backup_zip,
        data_dir=src_data,
        store_dir=src_store,
    )
    assert res["status"] == "success"
    assert backup_zip.exists()
    assert backup_zip.stat().st_size > 0

    # 2. Verify backup
    info = verify_backup(backup_zip)
    assert info["is_valid"] is True
    assert "manifest.json" in info["files"]
    assert "data/sample.pdf" in info["files"]
    assert "data/notes.txt" in info["files"]
    assert "storage/users.json" in info["files"]
    assert "storage/lexical_index.sqlite3" in info["files"]

    # 3. Restore to clean destination
    restore_data = tmp_path / "restored_data"
    restore_store = tmp_path / "restored_store"

    restored = restore_backup(
        archive_path=backup_zip,
        target_data_dir=restore_data,
        target_store_dir=restore_store,
    )
    assert restored["status"] == "restored"

    # Check restored files
    assert (restore_data / "sample.pdf").read_bytes() == b"%PDF-1.4 mock content"
    assert (restore_data / "notes.txt").read_text(encoding="utf-8") == "Confidential enterprise notes"
    assert (restore_store / "users.json").exists()
    restored_users = json.loads((restore_store / "users.json").read_text(encoding="utf-8"))
    assert restored_users[0]["email"] == "admin@enterprise.local"
    assert (restore_store / "lexical_index.sqlite3").read_bytes() == b"SQLite format 3\x00mockdb"

