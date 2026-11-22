from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from clearspend.database.settings import PostgreSQLSettings


class AdminConfigurationError(ValueError):
    """Raised when administrative PostgreSQL connection metadata is unsafe."""


REQUIRED_KEYS = frozenset(
    {
        "backend",
        "host",
        "port",
        "database",
        "user",
        "ssl_root_certificate",
        "keychain_service",
        "keychain_account",
    }
)
OPTIONAL_KEYS = frozenset(
    {
        "pool_min_size",
        "pool_max_size",
        "acquisition_timeout_seconds",
        "statement_timeout_milliseconds",
    }
)


def _required_text(values: dict[str, Any], key: str) -> str:
    value = values.get(key)
    if not isinstance(value, str) or not value.strip():
        raise AdminConfigurationError(f"PostgreSQL admin {key} is required")
    return value.strip()


def _path(config_path: Path, value: str) -> Path:
    candidate = Path(value).expanduser()
    if not candidate.is_absolute():
        candidate = config_path.parent / candidate
    return candidate.resolve()


def load_postgresql_admin_configuration(config_path: Path) -> PostgreSQLSettings:
    """Load an ignored admin connection file without accepting passwords."""
    try:
        raw = json.loads(config_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise AdminConfigurationError(
            "PostgreSQL admin configuration could not be read"
        ) from error
    if not isinstance(raw, dict):
        raise AdminConfigurationError(
            "PostgreSQL admin configuration must be an object"
        )
    values: dict[str, Any] = raw
    missing = REQUIRED_KEYS - values.keys()
    unknown = values.keys() - REQUIRED_KEYS - OPTIONAL_KEYS
    if missing:
        raise AdminConfigurationError(
            "PostgreSQL admin configuration is missing required fields"
        )
    if unknown:
        raise AdminConfigurationError(
            "PostgreSQL admin configuration contains unknown fields"
        )
    if values.get("backend") != "postgresql":
        raise AdminConfigurationError(
            "PostgreSQL admin configuration must select the postgresql backend"
        )
    try:
        return PostgreSQLSettings(
            host=_required_text(values, "host"),
            port=int(values["port"]),
            database=_required_text(values, "database"),
            user=_required_text(values, "user"),
            ssl_root_certificate=_path(
                config_path,
                _required_text(values, "ssl_root_certificate"),
            ),
            keychain_service=_required_text(values, "keychain_service"),
            keychain_account=_required_text(values, "keychain_account"),
            pool_min_size=int(values.get("pool_min_size", 1)),
            pool_max_size=int(values.get("pool_max_size", 2)),
            acquisition_timeout_seconds=float(
                values.get("acquisition_timeout_seconds", 15.0)
            ),
            statement_timeout_milliseconds=int(
                values.get("statement_timeout_milliseconds", 30_000)
            ),
        )
    except (TypeError, ValueError) as error:
        raise AdminConfigurationError(
            "PostgreSQL admin connection values are invalid"
        ) from error
