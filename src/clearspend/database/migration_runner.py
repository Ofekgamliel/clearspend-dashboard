from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from types import ModuleType
from typing import Sequence

from clearspend.database.migrations import v001_current_baseline


MIGRATION_TABLE_SQL = """CREATE TABLE IF NOT EXISTS schema_migrations (
  version INTEGER PRIMARY KEY,
  name TEXT NOT NULL UNIQUE,
  applied_at TEXT NOT NULL
)"""

DEFAULT_MIGRATIONS: tuple[ModuleType, ...] = (v001_current_baseline,)


class MigrationError(RuntimeError):
    """Raised when a database cannot be migrated safely."""


@dataclass(frozen=True)
class MigrationResult:
    starting_version: int
    ending_version: int
    applied_versions: tuple[int, ...]
    backup_path: Path | None


@dataclass(frozen=True)
class SchemaStatus:
    state: str
    version: int
    problems: tuple[str, ...]


def _connect(path: Path) -> sqlite3.Connection:
    connection = sqlite3.connect(path)
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def _table_names(connection: sqlite3.Connection) -> set[str]:
    return {
        row[0]
        for row in connection.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
        )
    }


def _current_version(connection: sqlite3.Connection) -> int:
    if "schema_migrations" not in _table_names(connection):
        return 0
    row = connection.execute("SELECT COALESCE(MAX(version),0) FROM schema_migrations").fetchone()
    return int(row[0])


def _validate_migrations(migrations: Sequence[ModuleType]) -> tuple[ModuleType, ...]:
    ordered = tuple(sorted(migrations, key=lambda migration: migration.VERSION))
    versions = [int(migration.VERSION) for migration in ordered]
    if versions != list(range(1, len(ordered) + 1)):
        raise MigrationError("Migration versions must be unique and contiguous from version 1")
    if any(not str(migration.NAME).strip() for migration in ordered):
        raise MigrationError("Every migration must have a name")
    return ordered


def inspect_database(path: Path) -> SchemaStatus:
    if not path.exists() or path.stat().st_size == 0:
        return SchemaStatus("empty", 0, ())
    connection = _connect(path)
    try:
        tables = _table_names(connection)
        version = _current_version(connection)
        if not tables:
            return SchemaStatus("empty", 0, ())
        if version > len(DEFAULT_MIGRATIONS):
            return SchemaStatus(
                "unsupported",
                version,
                (f"Schema version {version} is newer than this application supports",),
            )
        problems = tuple(v001_current_baseline.verify(connection))
        if problems:
            return SchemaStatus("unsupported", version, problems)
        return SchemaStatus("versioned" if version else "current_unversioned", version, ())
    finally:
        connection.close()


def _verified_backup(
    source: sqlite3.Connection,
    database_path: Path,
    backup_directory: Path,
    target_version: int,
) -> Path:
    backup_directory.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
    destination = (
        backup_directory
        / f"{database_path.stem}-before-schema-v{target_version}-{timestamp}.db"
    )
    backup = sqlite3.connect(destination)
    try:
        source.backup(backup)
        result = backup.execute("PRAGMA integrity_check").fetchone()[0]
        if result != "ok":
            raise MigrationError(f"Backup integrity check failed: {result}")
    finally:
        backup.close()
    return destination


def _record_migration(connection: sqlite3.Connection, migration: ModuleType) -> None:
    connection.execute(
        "INSERT INTO schema_migrations(version,name,applied_at) VALUES(?,?,?)",
        (migration.VERSION, migration.NAME, datetime.now().isoformat(timespec="seconds")),
    )


def migrate_database(
    path: Path,
    backup_directory: Path | None = None,
    *,
    migrations: Sequence[ModuleType] = DEFAULT_MIGRATIONS,
) -> MigrationResult:
    ordered = _validate_migrations(migrations)
    path.parent.mkdir(parents=True, exist_ok=True)
    existed_with_content = path.exists() and path.stat().st_size > 0
    connection = _connect(path)
    backup_path: Path | None = None
    applied: list[int] = []
    try:
        tables = _table_names(connection)
        version = _current_version(connection)
        starting_version = version
        if version > len(ordered):
            raise MigrationError(
                f"Database schema version {version} is newer than this application supports"
            )

        unversioned_tables = tables - {"schema_migrations"}
        if version == 0 and unversioned_tables:
            problems = v001_current_baseline.verify(connection)
            if problems:
                raise MigrationError("Unsupported unversioned schema: " + "; ".join(problems))

        has_pending_work = version < len(ordered)
        if has_pending_work and existed_with_content:
            if backup_directory is None:
                raise MigrationError("A backup directory is required before migrating an existing database")
            integrity = connection.execute("PRAGMA integrity_check").fetchone()[0]
            if integrity != "ok":
                raise MigrationError(f"Source database integrity check failed: {integrity}")
            backup_path = _verified_backup(connection, path, backup_directory, len(ordered))

        if version == 0 and unversioned_tables:
            connection.execute("BEGIN IMMEDIATE")
            try:
                connection.execute(MIGRATION_TABLE_SQL)
                _record_migration(connection, ordered[0])
                connection.commit()
            except Exception:
                connection.rollback()
                raise
            version = 1
            applied.append(1)

        for migration in ordered[version:]:
            connection.execute("BEGIN IMMEDIATE")
            try:
                connection.execute(MIGRATION_TABLE_SQL)
                migration.apply(connection)
                problems = migration.verify(connection)
                if problems:
                    raise MigrationError(
                        f"Migration {migration.VERSION} verification failed: " + "; ".join(problems)
                    )
                _record_migration(connection, migration)
                connection.commit()
            except Exception:
                connection.rollback()
                raise
            version = int(migration.VERSION)
            applied.append(version)

        final_problems = v001_current_baseline.verify(connection)
        if final_problems:
            raise MigrationError("Current schema verification failed: " + "; ".join(final_problems))
        return MigrationResult(starting_version, version, tuple(applied), backup_path)
    finally:
        connection.close()
