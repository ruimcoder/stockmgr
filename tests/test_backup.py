"""Tests for database backup and restore utilities."""
import time
from pathlib import Path
import pytest
from app.backup_utils import create_backup, list_backups, restore_backup, MAX_BACKUPS

@pytest.fixture
def tmp_db(tmp_path):
    db = tmp_path / "test.db"
    db.write_bytes(b"SQLite format 3\x00" + b"\x00" * 96)
    return db

def test_create_backup_creates_file(tmp_db):
    backup = create_backup(tmp_db)
    assert backup is not None
    assert backup.exists()
    assert "backup" in backup.name

def test_backup_naming_contains_timestamp(tmp_db):
    backup = create_backup(tmp_db)
    assert "_backup_" in backup.name
    assert backup.suffix == ".db"

def test_list_backups_newest_first(tmp_db):
    create_backup(tmp_db)
    time.sleep(1.1)
    create_backup(tmp_db)
    backups = list_backups(tmp_db)
    assert len(backups) >= 2
    assert backups[0]["filename"] > backups[1]["filename"]  # lexicographic = chronological

def test_prune_keeps_max_backups(tmp_db):
    for _ in range(MAX_BACKUPS + 3):
        create_backup(tmp_db)
        time.sleep(0.05)
    backups = list_backups(tmp_db)
    assert len(backups) <= MAX_BACKUPS

def test_restore_backup(tmp_db):
    original_content = tmp_db.read_bytes()
    backup = create_backup(tmp_db)
    # Corrupt the DB
    tmp_db.write_bytes(b"corrupted")
    result = restore_backup(tmp_db, backup.name)
    assert result is True
    assert tmp_db.read_bytes() == original_content

def test_restore_nonexistent_returns_false(tmp_db):
    result = restore_backup(tmp_db, "nonexistent_backup_99999999_999999.db")
    assert result is False

def test_create_backup_returns_none_if_no_db(tmp_path):
    db = tmp_path / "missing.db"
    result = create_backup(db)
    assert result is None
