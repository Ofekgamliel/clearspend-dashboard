from __future__ import annotations

import hashlib
import json
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Mapping, Sequence, Tuple

from clearspend.database.migration_runner import inspect_database_connection
from clearspend.database.postgresql import PostgreSQLPool


@dataclass(frozen=True)
class CopyTable:
    name: str
    columns: Tuple[str, ...]
    key_columns: Tuple[str, ...]
    boolean_columns: Tuple[str, ...] = ()


TABLES = (
    CopyTable(
        "imports",
        (
            "id", "original_name", "source_path", "byte_hash", "semantic_hash",
            "source_format", "provider", "card_last4", "product_name",
            "statement_range", "status", "parsed_rows", "inserted_rows",
            "duplicate_rows", "imported_at", "error_message",
        ),
        ("id",),
    ),
    CopyTable(
        "income_imports",
        (
            "id", "original_name", "source_path", "byte_hash", "source_format",
            "status", "parsed_rows", "inserted_rows", "duplicate_rows",
            "imported_at", "error_message",
        ),
        ("id",),
    ),
    CopyTable(
        "transactions",
        (
            "id", "transaction_key", "base_key", "occurrence", "provider",
            "card_last4", "source_sheet", "transaction_date", "billing_date",
            "billing_month", "billing_month_source", "installment_number",
            "installment_total", "merchant_raw", "merchant_normalized",
            "charged_amount", "charged_currency", "original_amount",
            "original_currency", "provider_category", "user_category",
            "user_subcategory", "transaction_type", "voucher_number", "notes",
            "execution_method", "exchange_rate", "source_payload",
            "first_import_id", "created_at",
        ),
        ("id",),
    ),
    CopyTable(
        "income_entries",
        ("id", "month", "source_name", "amount", "entry_key", "first_import_id", "created_at"),
        ("id",),
    ),
    CopyTable(
        "merchant_mappings",
        ("merchant_normalized", "category", "subcategory", "updated_at"),
        ("merchant_normalized",),
    ),
    CopyTable(
        "merchant_display_mappings",
        ("merchant_normalized", "canonical_group_id", "display_name", "updated_at"),
        ("merchant_normalized",),
    ),
    CopyTable(
        "transaction_category_overrides",
        ("transaction_id", "category", "subcategory", "updated_at"),
        ("transaction_id",),
    ),
    CopyTable(
        "transaction_spending_adjustments",
        (
            "transaction_id", "adjustment_type", "reimbursed_amount",
            "reimbursement_date", "note", "updated_at",
        ),
        ("transaction_id",),
    ),
    CopyTable(
        "import_coverage",
        (
            "import_id", "card_last4", "statement_month", "statement_period",
            "statement_as_of_date", "purchase_date_from", "purchase_date_to",
            "billing_date_from", "billing_date_to", "finalized_rows",
            "pending_rows", "outside_cycle_rows", "official_total",
        ),
        ("import_id", "card_last4"),
    ),
    CopyTable(
        "recurring_profiles",
        (
            "canonical_group_id", "display_name", "verdict", "recurring_type",
            "cadence", "cadence_months", "lifecycle_status", "end_month",
            "review_count", "updated_at",
        ),
        ("canonical_group_id",),
    ),
    CopyTable(
        "recurring_profile_members",
        ("canonical_group_id", "merchant_normalized", "included", "updated_at"),
        ("canonical_group_id", "merchant_normalized"),
        ("included",),
    ),
    CopyTable(
        "observation_reviews",
        (
            "finding_key", "observation_type", "resolution", "month",
            "transaction_ids", "recurring_series_id", "occurrence_start",
            "occurrence_end", "merchant_label", "active", "reviewed_at",
            "updated_at",
        ),
        ("finding_key",),
        ("active",),
    ),
    CopyTable(
        "events",
        (
            "id", "name", "event_type", "destination", "icon", "start_date",
            "end_date", "status", "budget", "notes", "created_at", "updated_at",
        ),
        ("id",),
    ),
    CopyTable(
        "event_transactions",
        ("transaction_id", "event_id", "assigned_at"),
        ("transaction_id",),
    ),
    CopyTable(
        "import_transactions",
        ("import_id", "transaction_id", "was_duplicate"),
        ("import_id", "transaction_id"),
    ),
)

IDENTITY_TABLES = ("imports", "transactions", "income_imports", "income_entries")
SOURCE_PATH_POLICIES = frozenset({"preserve", "filename", "redact"})


@dataclass(frozen=True)
class MigrationDataPolicy:
    source_paths: str
    preserve_statement_filenames: bool
    preserve_error_messages: bool
    preserve_source_payloads: bool

    def __post_init__(self) -> None:
        if self.source_paths not in SOURCE_PATH_POLICIES:
            raise ValueError("Unknown source-path migration policy")
        if not self.preserve_statement_filenames and self.source_paths != "redact":
            raise ValueError(
                "Removing statement filenames also requires redacting source paths"
            )


APPROVED_POSTGRESQL_MIGRATION_POLICY = MigrationDataPolicy(
    source_paths="filename",
    preserve_statement_filenames=True,
    preserve_error_messages=False,
    preserve_source_payloads=False,
)


@dataclass(frozen=True)
class PostgreSQLCopyResult:
    row_counts: Mapping[str, int]
    table_hashes: Mapping[str, str]


class PostgreSQLCopyError(RuntimeError):
    """Raised when a SQLite-to-PostgreSQL copy cannot be proven exact."""


def _source_connection(path: Path) -> sqlite3.Connection:
    connection = sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA query_only = ON")
    return connection


def _policy_row(
    table: CopyTable,
    row: Mapping[str, Any],
    policy: MigrationDataPolicy,
) -> Dict[str, Any]:
    values = {column: row[column] for column in table.columns}
    for column in table.boolean_columns:
        values[column] = bool(values[column])

    if table.name in {"imports", "income_imports"}:
        if not policy.preserve_statement_filenames:
            prefix = "statement" if table.name == "imports" else "income"
            values["original_name"] = f"{prefix}-{values['id']}"
        if policy.source_paths == "filename":
            values["source_path"] = values["original_name"]
        elif policy.source_paths == "redact":
            values["source_path"] = "migrated"
        if not policy.preserve_error_messages:
            values["error_message"] = None
    if table.name == "transactions" and not policy.preserve_source_payloads:
        values["source_payload"] = None
    return values


def _hash_rows(rows: Sequence[Mapping[str, Any]], columns: Sequence[str]) -> str:
    digest = hashlib.sha256()
    encoded_rows = []
    for row in rows:
        encoded = json.dumps(
            [row[column] for column in columns],
            ensure_ascii=False,
            separators=(",", ":"),
        ).encode("utf-8")
        encoded_rows.append(encoded)
    # Database collations can return identical text keys in a different order.
    # Sort canonical row bytes here so the content proof is engine-independent;
    # API parity separately verifies user-visible ordering.
    for encoded in sorted(encoded_rows):
        digest.update(len(encoded).to_bytes(8, "big"))
        digest.update(encoded)
    return digest.hexdigest()


def _ordered_select(table: CopyTable, schema: str = "") -> str:
    relation = f"{schema}.{table.name}" if schema else table.name
    return (
        f"SELECT {','.join(table.columns)} FROM {relation} "
        f"ORDER BY {','.join(table.key_columns)}"
    )


def _destination_rows(connection: Any, table: CopyTable) -> list[Mapping[str, Any]]:
    return list(connection.execute(_ordered_select(table, "clearspend")).fetchall())


def _validate_source(connection: sqlite3.Connection) -> None:
    status = inspect_database_connection(connection)
    if status.state not in {"current_unversioned", "versioned"}:
        raise PostgreSQLCopyError(
            "SQLite source schema is not a supported current ClearSpend database"
        )


def _validate_destination(connection: Any) -> None:
    role = connection.execute(
        "SELECT current_user AS current_user"
    ).fetchone()
    if role is None or str(role["current_user"]) != "postgres":
        raise PostgreSQLCopyError(
            "PostgreSQL copy requires the explicit administrative role"
        )
    history = connection.execute(
        "SELECT version,name FROM clearspend.schema_migrations ORDER BY version"
    ).fetchall()
    actual_history = [(int(row["version"]), str(row["name"])) for row in history]
    expected_history = [
        (1, "observation_reviews"),
        (2, "transaction_browsing"),
        (3, "merchant_management"),
        (4, "import_linkage"),
    ]
    if actual_history != expected_history:
        raise PostgreSQLCopyError("PostgreSQL destination migration history is not current")
    for table in TABLES:
        row = connection.execute(
            f"SELECT COUNT(*) AS row_count FROM clearspend.{table.name}"
        ).fetchone()
        if int(row["row_count"]) != 0:
            raise PostgreSQLCopyError("PostgreSQL destination is not empty")


def _advance_identity_sequences(connection: Any) -> None:
    for table in IDENTITY_TABLES:
        connection.execute(
            f"""SELECT setval(
            pg_get_serial_sequence('clearspend.{table}','id'),
            COALESCE((SELECT MAX(id) FROM clearspend.{table}),1),
            EXISTS(SELECT 1 FROM clearspend.{table})
            )"""
        )


def copy_sqlite_to_postgresql(
    source_path: Path,
    destination_pool: PostgreSQLPool,
    policy: MigrationDataPolicy,
) -> PostgreSQLCopyResult:
    """Copy current SQLite state atomically using an administrative pool."""
    source = _source_connection(source_path)
    counts: Dict[str, int] = {}
    hashes: Dict[str, str] = {}
    try:
        _validate_source(source)
        integrity = source.execute("PRAGMA integrity_check").fetchone()[0]
        if integrity != "ok":
            raise PostgreSQLCopyError("SQLite source integrity check failed")
        if source.execute("PRAGMA foreign_key_check").fetchone() is not None:
            raise PostgreSQLCopyError("SQLite source contains invalid foreign-key references")
        source.execute("BEGIN")

        with destination_pool.connection() as destination:
            try:
                _validate_destination(destination)
                for table in TABLES:
                    source_rows = [
                        _policy_row(table, row, policy)
                        for row in source.execute(_ordered_select(table)).fetchall()
                    ]
                    if source_rows:
                        placeholders = ",".join("?" for _ in table.columns)
                        statement = (
                            f"INSERT INTO clearspend.{table.name}"
                            f"({','.join(table.columns)}) VALUES({placeholders})"
                        )
                        destination.executemany(
                            statement,
                            [tuple(row[column] for column in table.columns) for row in source_rows],
                        )
                    destination_rows = _destination_rows(destination, table)
                    source_hash = _hash_rows(source_rows, table.columns)
                    destination_hash = _hash_rows(destination_rows, table.columns)
                    if len(destination_rows) != len(source_rows):
                        raise PostgreSQLCopyError(
                            f"PostgreSQL row-count mismatch for {table.name}"
                        )
                    if destination_hash != source_hash:
                        raise PostgreSQLCopyError(
                            f"PostgreSQL content mismatch for {table.name}"
                        )
                    counts[table.name] = len(source_rows)
                    hashes[table.name] = source_hash
                _advance_identity_sequences(destination)
                destination.commit()
            except BaseException:
                destination.rollback()
                raise
        source.rollback()
        return PostgreSQLCopyResult(dict(counts), dict(hashes))
    finally:
        source.close()
