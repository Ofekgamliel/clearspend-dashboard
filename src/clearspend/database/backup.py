from __future__ import annotations

import sqlite3
from datetime import datetime
from pathlib import Path


class DatabaseBackupError(RuntimeError):
    """Raised when a required SQLite backup cannot be created and verified."""


def create_verified_backup(
    source: sqlite3.Connection,
    database_path: Path,
    backup_directory: Path,
    label: str,
) -> Path:
    """Create an SQLite-consistent backup and verify both source and destination."""
    source_result = source.execute("PRAGMA integrity_check").fetchone()[0]
    if source_result != "ok":
        raise DatabaseBackupError(f"Source database integrity check failed: {source_result}")

    backup_directory.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
    destination = backup_directory / f"{database_path.stem}-{label}-{timestamp}.db"
    backup = sqlite3.connect(destination)
    try:
        source.backup(backup)
        backup_result = backup.execute("PRAGMA integrity_check").fetchone()[0]
        if backup_result != "ok":
            raise DatabaseBackupError(f"Backup integrity check failed: {backup_result}")
    except Exception:
        backup.close()
        destination.unlink(missing_ok=True)
        raise
    else:
        backup.close()
    return destination
