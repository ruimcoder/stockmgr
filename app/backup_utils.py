"""Database backup and restore utilities."""
from pathlib import Path
from datetime import datetime, UTC
import shutil
import logging
import uuid

BACKUP_DIR_NAME = "backups"
MAX_BACKUPS = 10

def get_backup_dir(db_path: Path) -> Path:
    """Return (and create) the backups/ directory next to the DB file."""
    backup_dir = db_path.parent / BACKUP_DIR_NAME
    backup_dir.mkdir(exist_ok=True)
    return backup_dir

def create_backup(db_path: Path) -> Path | None:
    """Copy db_path to backups/stockmgr_backup_YYYYMMDD_HHMMSS_<uid>.db.
    Returns the backup path, or None if db_path does not exist."""
    if not db_path.exists():
        return None
    backup_dir = get_backup_dir(db_path)
    ts = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
    uid = uuid.uuid4().hex[:6]
    stem = db_path.stem
    backup_path = backup_dir / f"{stem}_backup_{ts}_{uid}.db"
    shutil.copy2(db_path, backup_path)
    logging.getLogger(__name__).info("DB backup created: %s (%d bytes)", backup_path, backup_path.stat().st_size)
    _prune_old_backups(backup_dir, stem)
    return backup_path

def list_backups(db_path: Path) -> list[dict]:
    """Return list of backup dicts sorted newest-first: {filename, size_bytes, created_at}."""
    backup_dir = get_backup_dir(db_path)
    stem = db_path.stem
    backups = []
    for f in sorted(backup_dir.glob(f"{stem}_backup_*.db"), reverse=True):
        stat = f.stat()
        backups.append({
            "filename": f.name,
            "size_bytes": stat.st_size,
            "created_at": datetime.fromtimestamp(stat.st_mtime, UTC).isoformat(),
        })
    return backups

def restore_backup(db_path: Path, filename: str) -> bool:
    """Replace db_path with the named backup file. Returns True on success."""
    backup_dir = get_backup_dir(db_path)
    stem = db_path.stem
    # Scan the backup directory and match by name — never construct a path from user input.
    # This prevents path traversal: the path comes from filesystem enumeration, not from filename.
    backup_file: Path | None = None
    for candidate in backup_dir.glob(f"{stem}_backup_*.db"):
        if candidate.name == filename:
            backup_file = candidate
            break
    if backup_file is None:
        return False
    # Create a safety backup of current DB before restoring
    if db_path.exists():
        create_backup(db_path)
    shutil.copy2(backup_file, db_path)
    logging.getLogger(__name__).info("DB restored from: %s", backup_file.name)
    return True

def _prune_old_backups(backup_dir: Path, stem: str) -> None:
    """Keep only the MAX_BACKUPS most recent backups."""
    all_backups = sorted(backup_dir.glob(f"{stem}_backup_*.db"), reverse=True)
    for old in all_backups[MAX_BACKUPS:]:
        old.unlink()
        logging.getLogger(__name__).info("Pruned old backup: %s", old.name)
