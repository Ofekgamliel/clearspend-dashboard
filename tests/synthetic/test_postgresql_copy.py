from __future__ import annotations

import re
import sqlite3
import tempfile
import unittest
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator, Sequence

from clearspend.database.migration_runner import migrate_database
from clearspend.database.postgresql_copy import (
    APPROVED_POSTGRESQL_MIGRATION_POLICY,
    MigrationDataPolicy,
    PostgreSQLCopyError,
    TABLES,
    _hash_rows,
    copy_sqlite_to_postgresql,
)


class Result:
    def __init__(self, rows: Sequence[dict[str, Any]]) -> None:
        self.rows = list(rows)

    def fetchall(self) -> list[dict[str, Any]]:
        return list(self.rows)

    def fetchone(self) -> dict[str, Any] | None:
        return self.rows[0] if self.rows else None


class SyntheticPostgreSQLConnection:
    def __init__(self) -> None:
        self.rows = {table.name: [] for table in TABLES}
        self.commits = 0
        self.rollbacks = 0
        self.sequence_updates = 0

    def execute(self, sql: str, parameters: Sequence[Any] | None = None) -> Result:
        normalized = " ".join(sql.split())
        if normalized == "SELECT current_user AS current_user":
            return Result([{"current_user": "postgres"}])
        if normalized.startswith("SELECT version,name FROM clearspend.schema_migrations"):
            return Result(
                [
                    {"version": 1, "name": "observation_reviews"},
                    {"version": 2, "name": "transaction_browsing"},
                    {"version": 3, "name": "merchant_management"},
                    {"version": 4, "name": "import_linkage"},
                ]
            )
        count_match = re.fullmatch(
            r"SELECT COUNT\(\*\) AS row_count FROM clearspend\.([a-z_]+)",
            normalized,
        )
        if count_match:
            return Result([{"row_count": len(self.rows[count_match.group(1)])}])
        select_match = re.fullmatch(
            r"SELECT (.+) FROM clearspend\.([a-z_]+) ORDER BY (.+)",
            normalized,
        )
        if select_match:
            columns = select_match.group(1).split(",")
            table = select_match.group(2)
            keys = select_match.group(3).split(",")
            rows = sorted(self.rows[table], key=lambda row: tuple(row[key] for key in keys))
            return Result([{column: row[column] for column in columns} for row in rows])
        if normalized.startswith("SELECT setval("):
            self.sequence_updates += 1
            return Result([])
        raise AssertionError(f"Unexpected synthetic PostgreSQL query: {normalized}")

    def executemany(self, sql: str, parameters: Sequence[Sequence[Any]]) -> None:
        match = re.match(
            r"INSERT INTO clearspend\.([a-z_]+)\(([^)]+)\) VALUES",
            " ".join(sql.split()),
        )
        if match is None:
            raise AssertionError(f"Unexpected synthetic PostgreSQL insert: {sql}")
        table = match.group(1)
        columns = match.group(2).split(",")
        self.rows[table].extend(
            dict(zip(columns, values)) for values in parameters
        )

    def commit(self) -> None:
        self.commits += 1

    def rollback(self) -> None:
        self.rollbacks += 1


class SyntheticPostgreSQLPool:
    def __init__(self, connection: SyntheticPostgreSQLConnection) -> None:
        self.synthetic_connection = connection

    @contextmanager
    def connection(self) -> Iterator[SyntheticPostgreSQLConnection]:
        yield self.synthetic_connection


def seed_source(path: Path) -> None:
    migrate_database(path)
    connection = sqlite3.connect(path)
    try:
        connection.execute(
            """INSERT INTO imports(
            id,original_name,source_path,byte_hash,source_format,provider,card_last4,
            status,parsed_rows,inserted_rows,duplicate_rows,imported_at,error_message
            ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                7,
                "synthetic-statement.xlsx",
                "/synthetic/source/synthetic-statement.xlsx",
                "synthetic-byte-hash",
                "xlsx",
                "synthetic-provider",
                "0000",
                "failed",
                1,
                1,
                0,
                "2030-01-01T00:00:00",
                "synthetic parser diagnostic",
            ),
        )
        connection.execute(
            """INSERT INTO transactions(
            id,transaction_key,base_key,occurrence,provider,card_last4,source_sheet,
            merchant_raw,merchant_normalized,source_payload,first_import_id,created_at
            ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                11,
                "synthetic-transaction-key",
                "synthetic-base-key",
                1,
                "synthetic-provider",
                "0000",
                "synthetic-sheet",
                "Synthetic Merchant",
                "synthetic merchant",
                '{"synthetic":"raw payload"}',
                7,
                "2030-01-01T00:00:00",
            ),
        )
        connection.execute(
            """INSERT INTO income_imports(
            id,original_name,source_path,byte_hash,source_format,status,
            parsed_rows,inserted_rows,duplicate_rows,imported_at,error_message
            ) VALUES(?,?,?,?,?,?,?,?,?,?,?)""",
            (
                3,
                "synthetic-income.xlsx",
                "/synthetic/source/synthetic-income.xlsx",
                "synthetic-income-hash",
                "xlsx",
                "imported",
                1,
                1,
                0,
                "2030-01-01T00:00:00",
                "synthetic historical income diagnostic",
            ),
        )
        connection.execute(
            """INSERT INTO income_entries(
            id,month,source_name,amount,entry_key,first_import_id,created_at
            ) VALUES(?,?,?,?,?,?,?)""",
            (
                4,
                "2030-01",
                "Synthetic Contributor",
                "12345.67",
                "synthetic-income-entry",
                3,
                "2030-01-01T00:00:00",
            ),
        )
        connection.execute(
            """INSERT INTO merchant_mappings(
            merchant_normalized,category,subcategory,updated_at
            ) VALUES(?,?,?,?)""",
            ("synthetic merchant", "Household", "Supplies", "2030-01-01"),
        )
        connection.execute(
            """INSERT INTO merchant_display_mappings(
            merchant_normalized,canonical_group_id,display_name,updated_at
            ) VALUES(?,?,?,?)""",
            (
                "synthetic merchant",
                "synthetic-group",
                "Synthetic Merchant Group",
                "2030-01-01",
            ),
        )
        connection.execute(
            """INSERT INTO transaction_category_overrides(
            transaction_id,category,subcategory,updated_at
            ) VALUES(?,?,?,?)""",
            (11, "Travel", "Transit", "2030-01-02"),
        )
        connection.execute(
            """INSERT INTO transaction_spending_adjustments(
            transaction_id,adjustment_type,reimbursed_amount,reimbursement_date,note,updated_at
            ) VALUES(?,?,?,?,?,?)""",
            (
                11,
                "partial_reimbursement",
                "3.25",
                "2030-01-03",
                "Synthetic reimbursement",
                "2030-01-03",
            ),
        )
        connection.execute(
            """INSERT INTO import_coverage(
            import_id,card_last4,statement_month,statement_period,statement_as_of_date,
            purchase_date_from,purchase_date_to,billing_date_from,billing_date_to,
            finalized_rows,pending_rows,outside_cycle_rows,official_total
            ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                7,
                "0000",
                "2030-01",
                "2030-01-01/2030-01-31",
                "2030-01-31",
                "2030-01-01",
                "2030-01-31",
                "2030-02-01",
                "2030-02-01",
                1,
                1,
                0,
                "10.00",
            ),
        )
        connection.execute(
            """INSERT INTO recurring_profiles(
            canonical_group_id,display_name,verdict,lifecycle_status,review_count,updated_at
            ) VALUES(?,?,?,?,?,?)""",
            ("synthetic-group", "Synthetic Group", "recurring", "active", 1, "2030-01-01"),
        )
        connection.execute(
            """INSERT INTO recurring_profile_members(
            canonical_group_id,merchant_normalized,included,updated_at
            ) VALUES(?,?,?,?)""",
            ("synthetic-group", "synthetic merchant", 0, "2030-01-01"),
        )
        connection.execute(
            """INSERT INTO observation_reviews(
            finding_key,observation_type,resolution,month,active,reviewed_at,updated_at
            ) VALUES(?,?,?,?,?,?,?)""",
            (
                "synthetic-finding",
                "unusual_purchase",
                "expected",
                "2030-01",
                1,
                "2030-01-01",
                "2030-01-01",
            ),
        )
        connection.execute(
            """INSERT INTO events(
            id,name,event_type,destination,icon,start_date,end_date,status,budget,
            notes,created_at,updated_at
            ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                "synthetic-event",
                "Synthetic Trip",
                "trip",
                "Synthetic Destination",
                "✈️",
                "2030-01-01",
                "2030-01-31",
                "completed",
                "1000.00",
                "Synthetic notes",
                "2030-01-01",
                "2030-01-01",
            ),
        )
        connection.execute(
            """INSERT INTO event_transactions(transaction_id,event_id,assigned_at)
            VALUES(?,?,?)""",
            (11, "synthetic-event", "2030-01-02"),
        )
        connection.execute(
            """INSERT INTO import_transactions(import_id,transaction_id,was_duplicate)
            VALUES(?,?,?)""",
            (7, 11, 0),
        )
        connection.commit()
    finally:
        connection.close()


class PostgreSQLCopyTests(unittest.TestCase):
    def test_content_hash_is_independent_of_database_collation_order(self) -> None:
        rows = [
            {"key": "זברה", "value": "one"},
            {"key": "apple", "value": "two"},
        ]

        self.assertEqual(
            _hash_rows(rows, ("key", "value")),
            _hash_rows(list(reversed(rows)), ("key", "value")),
        )

    def test_copy_is_ordered_exact_atomic_and_applies_explicit_minimization(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "source.db"
            seed_source(path)
            destination = SyntheticPostgreSQLConnection()
            result = copy_sqlite_to_postgresql(
                path,
                SyntheticPostgreSQLPool(destination),  # type: ignore[arg-type]
                APPROVED_POSTGRESQL_MIGRATION_POLICY,
            )

            self.assertTrue(all(count == 1 for count in result.row_counts.values()))
            self.assertEqual(destination.commits, 1)
            self.assertEqual(destination.rollbacks, 0)
            self.assertEqual(destination.sequence_updates, 4)
            copied_import = destination.rows["imports"][0]
            self.assertEqual(copied_import["original_name"], "synthetic-statement.xlsx")
            self.assertEqual(copied_import["source_path"], "synthetic-statement.xlsx")
            self.assertIsNone(copied_import["error_message"])
            self.assertIsNone(destination.rows["transactions"][0]["source_payload"])
            self.assertIs(
                destination.rows["recurring_profile_members"][0]["included"],
                False,
            )
            self.assertIs(destination.rows["observation_reviews"][0]["active"], True)
            self.assertEqual(set(result.table_hashes), {table.name for table in TABLES})

            source = sqlite3.connect(path)
            try:
                self.assertEqual(
                    source.execute("SELECT original_name FROM imports").fetchone()[0],
                    "synthetic-statement.xlsx",
                )
            finally:
                source.close()

    def test_nonempty_destination_fails_before_copy_and_rolls_back(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "source.db"
            seed_source(path)
            destination = SyntheticPostgreSQLConnection()
            destination.rows["imports"].append({"id": 99})

            with self.assertRaisesRegex(PostgreSQLCopyError, "not empty"):
                copy_sqlite_to_postgresql(
                    path,
                    SyntheticPostgreSQLPool(destination),  # type: ignore[arg-type]
                    MigrationDataPolicy("preserve", True, True, True),
                )

            self.assertEqual(destination.commits, 0)
            self.assertEqual(destination.rollbacks, 1)
            self.assertEqual(destination.rows["imports"], [{"id": 99}])

    def test_runtime_role_is_rejected_before_any_copy(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "source.db"
            seed_source(path)
            destination = SyntheticPostgreSQLConnection()
            original_execute = destination.execute

            def execute(sql: str, parameters: Sequence[Any] | None = None) -> Result:
                if " ".join(sql.split()) == "SELECT current_user AS current_user":
                    return Result([{"current_user": "clearspend_app"}])
                return original_execute(sql, parameters)

            destination.execute = execute  # type: ignore[method-assign]

            with self.assertRaisesRegex(PostgreSQLCopyError, "administrative role"):
                copy_sqlite_to_postgresql(
                    path,
                    SyntheticPostgreSQLPool(destination),  # type: ignore[arg-type]
                    APPROVED_POSTGRESQL_MIGRATION_POLICY,
                )

            self.assertEqual(destination.commits, 0)
            self.assertEqual(destination.rollbacks, 1)
            self.assertTrue(all(not rows for rows in destination.rows.values()))

    def test_policy_requires_an_explicit_consistent_source_path_choice(self) -> None:
        with self.assertRaisesRegex(ValueError, "Unknown source-path"):
            MigrationDataPolicy("unknown", True, True, True)
        with self.assertRaisesRegex(ValueError, "requires redacting source paths"):
            MigrationDataPolicy("filename", False, True, True)
        with self.assertRaisesRegex(ValueError, "requires redacting source paths"):
            MigrationDataPolicy("preserve", False, True, True)


if __name__ == "__main__":
    unittest.main()
