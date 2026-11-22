from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from clearspend.database.postgresql_backup import PostgreSQLBackupConfiguration
from clearspend.database.settings import PostgreSQLSettings
from clearspend.database.supabase_region import validated_supabase_pooler_region


class RuntimeConfigurationError(ValueError):
    """Raised when local untracked runtime configuration is incomplete or unsafe."""


@dataclass(frozen=True)
class PostgreSQLRuntimeConfiguration:
    database: PostgreSQLSettings
    expected_region: str
    backup: PostgreSQLBackupConfiguration
    local_state_directory: Path


REQUIRED_KEYS = frozenset(
    {
        "backend",
        "expected_region",
        "host",
        "port",
        "database",
        "user",
        "ssl_root_certificate",
        "keychain_service",
        "keychain_account",
        "local_state_directory",
        "backup_directory",
        "backup_encryption_keychain_service",
        "backup_encryption_keychain_account",
    }
)
OPTIONAL_KEYS = frozenset(
    {
        "pool_min_size",
        "pool_max_size",
        "acquisition_timeout_seconds",
        "statement_timeout_milliseconds",
        "pg_dump_path",
        "psql_path",
        "pg_restore_path",
        "openssl_path",
    }
)


def _required_text(values: dict[str, Any], key: str) -> str:
    value = values.get(key)
    if not isinstance(value, str) or not value.strip():
        raise RuntimeConfigurationError(f"PostgreSQL runtime {key} is required")
    return value.strip()


def _path(config_path: Path, value: str) -> Path:
    candidate = Path(value).expanduser()
    if not candidate.is_absolute():
        candidate = config_path.parent / candidate
    return candidate.resolve()


def load_postgresql_runtime_configuration(
    config_path: Path,
) -> PostgreSQLRuntimeConfiguration:
    """Load endpoint metadata and Keychain references from an untracked JSON file."""
    try:
        raw = json.loads(config_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise RuntimeConfigurationError(
            "PostgreSQL runtime configuration could not be read"
        ) from error
    if not isinstance(raw, dict):
        raise RuntimeConfigurationError("PostgreSQL runtime configuration must be an object")
    values: dict[str, Any] = raw
    missing = REQUIRED_KEYS - values.keys()
    unknown = values.keys() - REQUIRED_KEYS - OPTIONAL_KEYS
    if missing:
        raise RuntimeConfigurationError(
            "PostgreSQL runtime configuration is missing required fields"
        )
    if unknown:
        raise RuntimeConfigurationError(
            "PostgreSQL runtime configuration contains unknown fields"
        )
    if values.get("backend") != "postgresql":
        raise RuntimeConfigurationError(
            "PostgreSQL runtime configuration must select the postgresql backend"
        )

    host = _required_text(values, "host")
    expected_region = _required_text(values, "expected_region")
    try:
        expected_region = validated_supabase_pooler_region(host, expected_region)
    except ValueError as error:
        raise RuntimeConfigurationError(
            f"PostgreSQL runtime {error}"
        ) from error

    certificate = _path(
        config_path,
        _required_text(values, "ssl_root_certificate"),
    )
    local_state_directory = _path(
        config_path,
        _required_text(values, "local_state_directory"),
    )
    backup_directory = _path(
        config_path,
        _required_text(values, "backup_directory"),
    )
    try:
        database = PostgreSQLSettings(
            host=host,
            port=int(values["port"]),
            database=_required_text(values, "database"),
            user=_required_text(values, "user"),
            ssl_root_certificate=certificate,
            keychain_service=_required_text(values, "keychain_service"),
            keychain_account=_required_text(values, "keychain_account"),
            pool_min_size=int(values.get("pool_min_size", 1)),
            pool_max_size=int(values.get("pool_max_size", 4)),
            acquisition_timeout_seconds=float(
                values.get("acquisition_timeout_seconds", 15.0)
            ),
            statement_timeout_milliseconds=int(
                values.get("statement_timeout_milliseconds", 15_000)
            ),
        )
    except (TypeError, ValueError) as error:
        raise RuntimeConfigurationError(
            "PostgreSQL runtime connection values are invalid"
        ) from error
    backup = PostgreSQLBackupConfiguration(
        directory=backup_directory,
        encryption_keychain_service=_required_text(
            values,
            "backup_encryption_keychain_service",
        ),
        encryption_keychain_account=_required_text(
            values,
            "backup_encryption_keychain_account",
        ),
        pg_dump_path=Path(str(values.get("pg_dump_path", "pg_dump"))).expanduser(),
        psql_path=Path(str(values.get("psql_path", "psql"))).expanduser(),
        pg_restore_path=Path(
            str(values.get("pg_restore_path", "pg_restore"))
        ).expanduser(),
        openssl_path=Path(str(values.get("openssl_path", "openssl"))).expanduser(),
    )
    return PostgreSQLRuntimeConfiguration(
        database,
        expected_region,
        backup,
        local_state_directory,
    )
