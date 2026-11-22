from __future__ import annotations

from dataclasses import dataclass
from types import ModuleType
from typing import Sequence

from clearspend.database.connection import database_connection, database_transaction
from clearspend.database.postgresql import PostgreSQLPool
from clearspend.database.postgresql_migrations import DEFAULT_POSTGRESQL_MIGRATIONS


MIGRATION_TABLE_SQL = """CREATE TABLE IF NOT EXISTS clearspend.schema_migrations (
  version INTEGER PRIMARY KEY,
  name TEXT NOT NULL UNIQUE,
  applied_at TEXT NOT NULL
)"""


class PostgreSQLMigrationError(RuntimeError):
    """Raised when a PostgreSQL schema cannot be migrated safely."""


@dataclass(frozen=True)
class PostgreSQLSchemaStatus:
    state: str
    version: int
    problems: tuple[str, ...]


@dataclass(frozen=True)
class PostgreSQLMigrationResult:
    starting_version: int
    ending_version: int
    applied_versions: tuple[int, ...]


def _validate_migrations(migrations: Sequence[ModuleType]) -> tuple[ModuleType, ...]:
    ordered = tuple(sorted(migrations, key=lambda migration: migration.VERSION))
    versions = [int(migration.VERSION) for migration in ordered]
    if versions != list(range(1, len(ordered) + 1)):
        raise PostgreSQLMigrationError(
            "PostgreSQL migration versions must be unique and contiguous from version 1"
        )
    if any(not str(migration.NAME).strip() for migration in ordered):
        raise PostgreSQLMigrationError("Every PostgreSQL migration must have a name")
    return ordered


def inspect_postgresql_schema(
    pool: PostgreSQLPool,
    *,
    migrations: Sequence[ModuleType] = DEFAULT_POSTGRESQL_MIGRATIONS,
) -> PostgreSQLSchemaStatus:
    ordered = _validate_migrations(migrations)
    with database_connection(pool) as connection:
        schema_row = connection.execute(
            "SELECT to_regnamespace('clearspend') IS NOT NULL AS schema_exists"
        ).fetchone()
        if not schema_row["schema_exists"]:
            return PostgreSQLSchemaStatus(
                "unprovisioned",
                0,
                ("Private schema clearspend does not exist",),
            )
        table_row = connection.execute(
            """SELECT to_regclass('clearspend.schema_migrations') IS NOT NULL
            AS table_exists"""
        ).fetchone()
        if not table_row["table_exists"]:
            return PostgreSQLSchemaStatus("empty", 0, ())
        history_rows = connection.execute(
            """SELECT version,name FROM clearspend.schema_migrations
            ORDER BY version"""
        ).fetchall()
    actual_history = [
        (int(row["version"]), str(row["name"])) for row in history_rows
    ]
    expected_history = [
        (int(migration.VERSION), str(migration.NAME))
        for migration in ordered[: len(actual_history)]
    ]
    version = actual_history[-1][0] if actual_history else 0
    if actual_history != expected_history:
        return PostgreSQLSchemaStatus(
            "unsupported",
            version,
            ("PostgreSQL migration history does not match this application",),
        )
    return PostgreSQLSchemaStatus("versioned" if actual_history else "empty", version, ())


def migrate_postgresql(
    pool: PostgreSQLPool,
    *,
    migrations: Sequence[ModuleType] = DEFAULT_POSTGRESQL_MIGRATIONS,
) -> PostgreSQLMigrationResult:
    """Apply verified migrations through an explicitly opened admin pool."""
    ordered = _validate_migrations(migrations)
    status = inspect_postgresql_schema(pool, migrations=ordered)
    if status.state == "unprovisioned":
        raise PostgreSQLMigrationError("PostgreSQL private schema is not provisioned")
    if status.state == "unsupported":
        raise PostgreSQLMigrationError("; ".join(status.problems))

    starting_version = status.version
    applied: list[int] = []
    for migration in ordered[starting_version:]:
        with database_transaction(pool) as connection:
            connection.execute(MIGRATION_TABLE_SQL)
            migration.apply(connection)
            problems = tuple(migration.verify(connection))
            if problems:
                raise PostgreSQLMigrationError(
                    f"PostgreSQL migration {migration.VERSION} verification failed: "
                    + "; ".join(problems)
                )
            connection.execute(
                """INSERT INTO clearspend.schema_migrations(version,name,applied_at)
                VALUES(?,?,CURRENT_TIMESTAMP::TEXT)""",
                (int(migration.VERSION), str(migration.NAME)),
            )
        applied.append(int(migration.VERSION))

    ending_version = applied[-1] if applied else starting_version
    return PostgreSQLMigrationResult(
        starting_version,
        ending_version,
        tuple(applied),
    )
