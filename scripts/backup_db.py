#!/usr/bin/env python
"""Standalone database backup script.

Usage:
    python scripts/backup_db.py
    python scripts/backup_db.py --db path/to/stockmgr.db --out backups/
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from app.backup_utils import create_backup, get_backup_dir

def main():
    parser = argparse.ArgumentParser(description="Backup the stockmgr SQLite database")
    parser.add_argument("--db", default="stockmgr.db", help="Path to DB file")
    parser.add_argument("--out", default=None, help="Output directory (default: backups/ next to DB)")
    args = parser.parse_args()
    db_path = Path(args.db).resolve()
    if not db_path.exists():
        print(f"ERROR: DB file not found: {db_path}", file=sys.stderr)
        sys.exit(1)
    backup_path = create_backup(db_path)
    if backup_path:
        print(f"Backup created: {backup_path}")
    else:
        print("Nothing to backup.")

if __name__ == "__main__":
    main()
