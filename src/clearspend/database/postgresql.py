from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
from typing import Any, Callable, Iterator, Optional, Sequence

from psycopg.conninfo import make_conninfo
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool, PoolTimeout

from clearspend.database.errors import DatabaseBusyError, DatabaseUnavailableError
from clearspend.database.keychain import load_keychain_password
from clearspend.database.settings import PostgreSQLSettings


PasswordLoader = Callable[[str, str], str]


def _postgresql_query(sql: str) -> str:
    """Translate the application's neutral qmark bindings for Psycopg.

    Feature SQL uses qmark placeholders because that is the established
    SQLite contract. PostgreSQL-specific SQL that needs a literal question
    mark or a question-mark operator must live in a PostgreSQL migration or
    adapter instead of passing through this function.
    """
    return sql.replace("?", "%s")


class PostgreSQLConnection:
    """Small compatibility facade over a pooled Psycopg connection."""

    def __init__(self, connection: Any) -> None:
        self._connection = connection

    def execute(self, sql: Any, parameters: Sequence[Any] | None = None) -> Any:
        query = _postgresql_query(sql) if isinstance(sql, str) else sql
        if parameters is None:
            return self._connection.execute(query)
        return self._connection.execute(query, parameters)

    def executemany(self, sql: Any, parameters: Sequence[Sequence[Any]]) -> None:
        query = _postgresql_query(sql) if isinstance(sql, str) else sql
        cursor = self._connection.cursor()
        try:
            cursor.executemany(query, parameters)
        finally:
            cursor.close()

    def commit(self) -> None:
        self._connection.commit()

    def rollback(self) -> None:
        self._connection.rollback()


def build_postgresql_conninfo(settings: PostgreSQLSettings, password: str) -> str:
    certificate = Path(settings.ssl_root_certificate)
    if not certificate.is_file():
        raise ValueError("PostgreSQL root certificate does not exist")
    return make_conninfo(
        host=settings.host,
        port=settings.port,
        dbname=settings.database,
        user=settings.user,
        password=password,
        sslmode="verify-full",
        sslrootcert=str(certificate),
        connect_timeout=max(1, int(settings.acquisition_timeout_seconds)),
        application_name="clearspend",
        options=f"-c statement_timeout={settings.statement_timeout_milliseconds}",
    )


class PostgreSQLPool:
    """Lazily opened, bounded pool for the local threaded server."""

    def __init__(
        self,
        settings: PostgreSQLSettings,
        *,
        password_loader: PasswordLoader = load_keychain_password,
    ) -> None:
        self.settings = settings
        self._password_loader = password_loader
        self._pool: Optional[ConnectionPool] = None

    @property
    def is_open(self) -> bool:
        return self._pool is not None

    def open(self) -> None:
        if self._pool is not None:
            return
        password = self._password_loader(
            self.settings.keychain_service,
            self.settings.keychain_account,
        )
        conninfo = build_postgresql_conninfo(self.settings, password)
        pool = ConnectionPool(
            conninfo,
            min_size=self.settings.pool_min_size,
            max_size=self.settings.pool_max_size,
            timeout=self.settings.acquisition_timeout_seconds,
            kwargs={"row_factory": dict_row},
            open=False,
            name="clearspend",
        )
        try:
            pool.open(wait=True, timeout=self.settings.acquisition_timeout_seconds)
        except BaseException as error:
            pool.close()
            if isinstance(error, Exception):
                raise DatabaseUnavailableError("PostgreSQL is unavailable") from error
            raise
        self._pool = pool

    @contextmanager
    def connection(self) -> Iterator[PostgreSQLConnection]:
        pool = self._pool
        if pool is None:
            raise DatabaseUnavailableError("PostgreSQL pool is not open")
        try:
            with pool.connection(
                timeout=self.settings.acquisition_timeout_seconds
            ) as connection:
                yield PostgreSQLConnection(connection)
        except PoolTimeout as error:
            raise DatabaseBusyError("PostgreSQL connection pool is busy") from error

    def close(self) -> None:
        pool, self._pool = self._pool, None
        if pool is not None:
            pool.close()
