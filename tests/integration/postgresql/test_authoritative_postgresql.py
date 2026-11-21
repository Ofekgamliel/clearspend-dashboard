from __future__ import annotations

import os
import tempfile
import unittest
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

import psycopg
from psycopg import sql
from psycopg.errors import InsufficientPrivilege
from psycopg.rows import dict_row

from clearspend.database.connection import database_transaction
from clearspend.database.postgresql import PostgreSQLConnection, PostgreSQLPool
from clearspend.database.postgresql_backup import (
    EXPECTED_CLEARSPEND_TABLES,
    PostgreSQLBackupConfiguration,
)
from clearspend.database.postgresql_migration_runner import (
    inspect_postgresql_schema,
    migrate_postgresql,
)
from clearspend.database.postgresql_provisioning import (
    API_ROLES,
    provision_postgresql,
)
from clearspend.database.settings import PostgreSQLSettings
from clearspend.staging.service import commit_staged_statement_postgresql
from clearspend.transactions.queries import transactions_payload
from clearspend.transactions.service import (
    save_transaction_adjustment,
    save_transaction_category,
)
from tests.synthetic.browser_seed import create_browser_statement


POSTGRES_HOST = os.environ.get("CLEARSPEND_TEST_POSTGRES_HOST", "")
POSTGRES_PORT = int(os.environ.get("CLEARSPEND_TEST_POSTGRES_PORT", "5432"))
POSTGRES_DATABASE = os.environ.get("CLEARSPEND_TEST_POSTGRES_DATABASE", "postgres")
POSTGRES_ADMIN_PASSWORD = os.environ.get("CLEARSPEND_TEST_POSTGRES_ADMIN_PASSWORD", "")
POSTGRES_RUNTIME_PASSWORD = os.environ.get("CLEARSPEND_TEST_POSTGRES_RUNTIME_PASSWORD", "")


class LocalPostgreSQLPool(PostgreSQLPool):
    """Use the production adapter against an isolated non-TLS CI service."""

    def __init__(self, user: str, password: str) -> None:
        settings = PostgreSQLSettings(
            host=POSTGRES_HOST,
            port=POSTGRES_PORT,
            database=POSTGRES_DATABASE,
            user=user,
            ssl_root_certificate=Path("unused-in-isolated-ci.crt"),
            keychain_service="unused-in-isolated-ci",
            keychain_account=user,
        )
        super().__init__(settings, password_loader=lambda service, account: password)
        self._test_password = password

    @contextmanager
    def connection(self) -> Iterator[PostgreSQLConnection]:
        with psycopg.connect(
            host=self.settings.host,
            port=self.settings.port,
            dbname=self.settings.database,
            user=self.settings.user,
            password=self._test_password,
            row_factory=dict_row,
        ) as connection:
            yield PostgreSQLConnection(connection)


@unittest.skipUnless(
    POSTGRES_HOST and POSTGRES_ADMIN_PASSWORD and POSTGRES_RUNTIME_PASSWORD,
    "Disposable PostgreSQL integration environment is not configured",
)
class AuthoritativePostgreSQLIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.admin_pool = LocalPostgreSQLPool("postgres", POSTGRES_ADMIN_PASSWORD)
        cls._create_supabase_api_roles()
        cls.provisioning = provision_postgresql(
            cls.admin_pool,
            POSTGRES_RUNTIME_PASSWORD,
            salt_factory=lambda size: bytes(range(size)),
        )
        cls.migration = migrate_postgresql(cls.admin_pool)
        cls.runtime_pool = LocalPostgreSQLPool(
            "clearspend_app",
            POSTGRES_RUNTIME_PASSWORD,
        )

    @classmethod
    def _admin_connection(cls):
        return psycopg.connect(
            host=POSTGRES_HOST,
            port=POSTGRES_PORT,
            dbname=POSTGRES_DATABASE,
            user="postgres",
            password=POSTGRES_ADMIN_PASSWORD,
            row_factory=dict_row,
        )

    @classmethod
    def _create_supabase_api_roles(cls) -> None:
        with cls._admin_connection() as connection:
            for role in API_ROLES:
                if role == "PUBLIC":
                    continue
                present = connection.execute(
                    "SELECT EXISTS(SELECT 1 FROM pg_roles WHERE rolname=%s) AS present",
                    (role,),
                ).fetchone()["present"]
                if not present:
                    connection.execute(
                        sql.SQL("CREATE ROLE {} NOLOGIN").format(sql.Identifier(role))
                    )

    def setUp(self) -> None:
        self._clear_application_rows()

    def tearDown(self) -> None:
        self._clear_application_rows()

    def _clear_application_rows(self) -> None:
        tables = sorted(EXPECTED_CLEARSPEND_TABLES - {"schema_migrations"})
        identifiers = sql.SQL(", ").join(
            sql.Identifier("clearspend", table) for table in tables
        )
        with self._admin_connection() as connection:
            connection.execute(
                sql.SQL("TRUNCATE TABLE {} RESTART IDENTITY CASCADE").format(
                    identifiers
                )
            )

    def _seed_transaction(self) -> int:
        with database_transaction(self.runtime_pool) as connection:
            import_id = connection.execute(
                """INSERT INTO imports(
                original_name,source_path,byte_hash,source_format,provider,
                card_last4,status,parsed_rows,inserted_rows,imported_at
                ) VALUES(?,?,?,?,?,?,?,?,?,?) RETURNING id""",
                (
                    "synthetic-ci.xlsx",
                    "synthetic-ci.xlsx",
                    "synthetic-ci-byte-hash",
                    ".xlsx",
                    "synthetic",
                    "0001",
                    "imported",
                    1,
                    1,
                    "2030-01-15T10:00:00+00:00",
                ),
            ).fetchone()["id"]
            return int(
                connection.execute(
                    """INSERT INTO transactions(
                    transaction_key,base_key,occurrence,provider,card_last4,
                    source_sheet,transaction_date,billing_month,
                    billing_month_source,merchant_raw,merchant_normalized,
                    charged_amount,charged_currency,provider_category,
                    first_import_id,created_at
                    ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?) RETURNING id""",
                    (
                        "synthetic-ci-transaction",
                        "synthetic-ci-base",
                        1,
                        "synthetic",
                        "0001",
                        "synthetic-sheet",
                        "2030-01-10",
                        "2030-01",
                        "statement",
                        "Synthetic CI Merchant",
                        "synthetic ci merchant",
                        "125.00",
                        "ILS",
                        "Household",
                        import_id,
                        "2030-01-15T10:00:00+00:00",
                    ),
                ).fetchone()["id"]
            )

    @staticmethod
    def _analysis(coverage: list[dict] | None = None) -> dict:
        return {
            "possible_duplicates": [],
            "merchants": [],
            "pending_transactions": [],
            "files": [{"coverage": coverage or []}],
        }

    @staticmethod
    def _backup_configuration() -> PostgreSQLBackupConfiguration:
        return PostgreSQLBackupConfiguration(
            Path(tempfile.gettempdir()) / "clearspend-ci-backups",
            "synthetic-ci-keychain",
            "synthetic-ci-archive",
        )

    def test_provisioning_and_all_migrations_are_real_and_repeatable(self) -> None:
        self.assertTrue(self.provisioning.role_created)
        self.assertEqual(self.migration.applied_versions, (1, 2, 3, 4))
        status = inspect_postgresql_schema(self.admin_pool)
        self.assertEqual((status.state, status.version), ("versioned", 4))
        second = migrate_postgresql(self.admin_pool)
        self.assertEqual(second.applied_versions, ())
        self.assertEqual(second.ending_version, 4)

    def test_runtime_role_reads_writes_and_cannot_create_schema_objects(self) -> None:
        transaction_id = self._seed_transaction()

        category = save_transaction_category(
            self.runtime_pool,
            transaction_id,
            "Synthetic reviewed category",
            "",
        )
        adjustment = save_transaction_adjustment(
            self.runtime_pool,
            transaction_id,
            25,
            "2030-01-20",
            "Synthetic CI reimbursement",
        )
        payload = transactions_payload(
            self.runtime_pool,
            "all",
            "all",
            complete_history=True,
        )

        self.assertEqual(category["status"], "saved")
        self.assertEqual(adjustment["status"], "saved")
        self.assertEqual(payload["total"], 1)
        self.assertEqual(payload["transactions"][0]["category"], "Synthetic reviewed category")
        self.assertEqual(payload["transactions"][0]["personal_amount"], 100.0)

        with self.runtime_pool.connection() as connection:
            with self.assertRaises(InsufficientPrivilege):
                connection.execute("CREATE TABLE clearspend.forbidden_ci_table(id INTEGER)")
            connection.rollback()

    def test_supabase_api_roles_have_no_private_schema_access(self) -> None:
        with self._admin_connection() as connection:
            rows = connection.execute(
                """SELECT role.rolname,
                has_schema_privilege(role.rolname,'clearspend','USAGE') AS can_use,
                has_schema_privilege(role.rolname,'clearspend','CREATE') AS can_create
                FROM pg_roles role
                WHERE role.rolname=ANY(%s)
                ORDER BY role.rolname""",
                ([role for role in API_ROLES if role != "PUBLIC"],),
            ).fetchall()
            exposed = connection.execute(
                """SELECT grantee,table_name,privilege_type
                FROM information_schema.table_privileges
                WHERE table_schema='clearspend'
                AND grantee=ANY(%s)""",
                (["PUBLIC", *[role for role in API_ROLES if role != "PUBLIC"]],),
            ).fetchall()

        self.assertEqual(len(rows), 3)
        self.assertTrue(all(not row["can_use"] and not row["can_create"] for row in rows))
        self.assertEqual(exposed, [])
        for role in (role for role in API_ROLES if role != "PUBLIC"):
            with self._admin_connection() as connection:
                connection.execute(
                    sql.SQL("SET ROLE {}").format(sql.Identifier(role))
                )
                with self.assertRaises(InsufficientPrivilege):
                    connection.execute("SELECT COUNT(*) FROM clearspend.transactions")
                connection.rollback()

    def test_reviewed_import_commits_against_real_postgresql(self) -> None:
        source = create_browser_statement()
        self.addCleanup(source.unlink, missing_ok=True)
        result = commit_staged_statement_postgresql(
            self.runtime_pool,
            self._backup_configuration(),
            {"uploads": [{"filename": "synthetic-ci-import.xlsx", "path": source}]},
            [],
            [],
            self._analysis(),
            backup_creator=lambda *args, **kwargs: Path("synthetic-ci-backup.dump.enc"),
        )

        with self.runtime_pool.connection() as connection:
            imported = connection.execute(
                """SELECT original_name,source_path,error_message
                FROM imports WHERE status='imported'"""
            ).fetchone()
            transaction = connection.execute(
                "SELECT source_payload FROM transactions"
            ).fetchone()

        self.assertEqual(result["status"], "committed")
        self.assertEqual(imported["original_name"], "synthetic-ci-import.xlsx")
        self.assertEqual(imported["source_path"], "synthetic-ci-import.xlsx")
        self.assertIsNone(imported["error_message"])
        self.assertIsNone(transaction["source_payload"])

    def test_failed_reviewed_import_rolls_back_every_real_write(self) -> None:
        source = create_browser_statement()
        self.addCleanup(source.unlink, missing_ok=True)
        with self.assertRaises(KeyError):
            commit_staged_statement_postgresql(
                self.runtime_pool,
                self._backup_configuration(),
                {"uploads": [{"filename": "synthetic-ci-rollback.xlsx", "path": source}]},
                [],
                [],
                self._analysis([{}]),
                backup_creator=lambda *args, **kwargs: Path(
                    "synthetic-ci-backup.dump.enc"
                ),
            )

        with self.runtime_pool.connection() as connection:
            imports = connection.execute(
                "SELECT COUNT(*) AS count FROM imports"
            ).fetchone()["count"]
            transactions = connection.execute(
                "SELECT COUNT(*) AS count FROM transactions"
            ).fetchone()["count"]
        self.assertEqual((imports, transactions), (0, 0))


if __name__ == "__main__":
    unittest.main()
