from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Union


class DatabaseBackend(str, Enum):
    SQLITE = "sqlite"
    POSTGRESQL = "postgresql"


@dataclass(frozen=True)
class PostgreSQLSettings:
    host: str
    port: int
    database: str
    user: str
    ssl_root_certificate: Path
    keychain_service: str
    keychain_account: str
    pool_min_size: int = 1
    pool_max_size: int = 4
    acquisition_timeout_seconds: float = 15.0
    statement_timeout_milliseconds: int = 15_000

    def __post_init__(self) -> None:
        for name in ("host", "database", "user", "keychain_service", "keychain_account"):
            if not str(getattr(self, name)).strip():
                raise ValueError(f"PostgreSQL {name} is required")
        if not 1 <= self.port <= 65_535:
            raise ValueError("PostgreSQL port must be between 1 and 65535")
        if self.pool_min_size < 1 or self.pool_max_size < self.pool_min_size:
            raise ValueError("PostgreSQL pool bounds are invalid")
        if self.acquisition_timeout_seconds <= 0:
            raise ValueError("PostgreSQL acquisition timeout must be positive")
        if self.statement_timeout_milliseconds <= 0:
            raise ValueError("PostgreSQL statement timeout must be positive")


@dataclass(frozen=True)
class DatabaseSettings:
    """Explicit settings for the supported archival SQLite connection path."""

    backend: DatabaseBackend
    sqlite_path: Path | None = None

    def __post_init__(self) -> None:
        if self.backend is not DatabaseBackend.SQLITE:
            raise ValueError("PostgreSQL requires an explicitly opened PostgreSQLPool")
        if self.sqlite_path is None:
            raise ValueError("SQLite database path is required")

    @classmethod
    def sqlite(cls, path: Path | str) -> DatabaseSettings:
        return cls(DatabaseBackend.SQLITE, Path(path))

DatabaseSource = Union[DatabaseSettings, Path, str]


def normalize_database_settings(source: DatabaseSource) -> DatabaseSettings:
    if isinstance(source, DatabaseSettings):
        return source
    return DatabaseSettings.sqlite(source)
