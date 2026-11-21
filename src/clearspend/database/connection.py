from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from typing import Any, Iterator, Union

from clearspend.database.postgresql import PostgreSQLPool
from clearspend.database.settings import (
    DatabaseBackend,
    DatabaseSource,
    normalize_database_settings,
)
from clearspend.database.sqlite import connect_sqlite


DatabaseTarget = Union[DatabaseSource, PostgreSQLPool]
POSTGRESQL_WRITE_LOCK_ID = 1_127_033_681


def acquire_authoritative_write_lock(connection: Any) -> None:
    """Serialize authoritative PostgreSQL writes with backup/import boundaries."""
    connection.execute(
        "SELECT pg_advisory_xact_lock(?)",
        (POSTGRESQL_WRITE_LOCK_ID,),
    )


def connect_database(
    source: DatabaseSource,
    *,
    row_factory: Any = sqlite3.Row,
    enforce_foreign_keys: bool = False,
) -> sqlite3.Connection:
    """Open an application database connection with explicit shared defaults.

    Foreign-key enforcement remains opt-in to preserve the established runtime
    behavior during this structural refactor. Migration connections enable it
    independently.
    """
    settings = normalize_database_settings(source)
    if settings.backend is not DatabaseBackend.SQLITE:
        raise RuntimeError(
            "PostgreSQL connections require an explicitly opened PostgreSQLPool"
        )
    if settings.sqlite_path is None:
        raise ValueError("SQLite database path is required")
    return connect_sqlite(
        settings.sqlite_path,
        row_factory=row_factory,
        enforce_foreign_keys=enforce_foreign_keys,
    )


@contextmanager
def database_connection(source: DatabaseTarget) -> Iterator[Any]:
    """Own one connection for a bounded read or caller-managed operation."""
    if isinstance(source, PostgreSQLPool):
        with source.connection() as connection:
            yield connection
        return
    connection = connect_database(source)
    try:
        yield connection
    finally:
        connection.close()


@contextmanager
def database_transaction(source: DatabaseTarget) -> Iterator[Any]:
    """Commit one complete operation or roll it back before releasing it."""
    if isinstance(source, PostgreSQLPool):
        with source.connection() as connection:
            try:
                acquire_authoritative_write_lock(connection)
                yield connection
                connection.commit()
            except BaseException:
                connection.rollback()
                raise
        return
    connection = connect_database(source)
    try:
        yield connection
        connection.commit()
    except BaseException:
        connection.rollback()
        raise
    finally:
        connection.close()
