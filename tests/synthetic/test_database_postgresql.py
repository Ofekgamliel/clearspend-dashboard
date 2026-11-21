from __future__ import annotations

import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from psycopg.conninfo import conninfo_to_dict
from psycopg import sql
from psycopg_pool import PoolTimeout

from clearspend.database.errors import DatabaseBusyError, DatabaseUnavailableError
from clearspend.database.keychain import KeychainPasswordError, load_keychain_password
from clearspend.database.postgresql import (
    PostgreSQLConnection,
    PostgreSQLPool,
    build_postgresql_conninfo,
)
from clearspend.database.settings import PostgreSQLSettings


class PostgreSQLInfrastructureTests(unittest.TestCase):
    def settings(self, certificate: Path) -> PostgreSQLSettings:
        return PostgreSQLSettings(
            host="db.synthetic.invalid",
            port=5432,
            database="postgres",
            user="clearspend_app",
            ssl_root_certificate=certificate,
            keychain_service="clearspend-synthetic",
            keychain_account="clearspend_app",
        )

    @patch("clearspend.database.keychain.subprocess.run")
    def test_keychain_password_uses_argument_list_and_returns_only_stdout(self, run: Mock) -> None:
        run.return_value = subprocess.CompletedProcess([], 0, "synthetic-secret\n", "")

        password = load_keychain_password("clearspend-synthetic", "clearspend_app")

        self.assertEqual(password, "synthetic-secret")
        run.assert_called_once_with(
            [
                "security",
                "find-generic-password",
                "-s",
                "clearspend-synthetic",
                "-a",
                "clearspend_app",
                "-w",
            ],
            capture_output=True,
            text=True,
            check=False,
        )

    @patch("clearspend.database.keychain.subprocess.run")
    def test_missing_keychain_password_raises_without_exposing_command_output(self, run: Mock) -> None:
        run.return_value = subprocess.CompletedProcess([], 44, "", "private diagnostic")

        with self.assertRaisesRegex(KeychainPasswordError, "was not found") as raised:
            load_keychain_password("clearspend-synthetic", "clearspend_app")

        self.assertNotIn("private diagnostic", str(raised.exception))

    def test_conninfo_requires_certificate_and_enforces_tls_and_timeout(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            certificate = Path(directory) / "ca.crt"
            certificate.touch()
            conninfo = build_postgresql_conninfo(
                self.settings(certificate),
                "synthetic-secret",
            )

        parameters = conninfo_to_dict(conninfo)
        self.assertEqual(parameters["sslmode"], "verify-full")
        self.assertEqual(parameters["sslrootcert"], str(certificate))
        self.assertEqual(parameters["user"], "clearspend_app")
        self.assertEqual(parameters["connect_timeout"], "15")
        self.assertEqual(parameters["options"], "-c statement_timeout=15000")

    def test_pool_is_lazy_bounded_and_idempotently_closed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            certificate = Path(directory) / "ca.crt"
            certificate.touch()
            settings = self.settings(certificate)
            password_loader = Mock(return_value="synthetic-secret")
            pool_instance = Mock()
            with patch(
                "clearspend.database.postgresql.ConnectionPool",
                return_value=pool_instance,
            ) as pool_factory:
                pool = PostgreSQLPool(settings, password_loader=password_loader)
                self.assertFalse(pool.is_open)

                pool.open()
                pool.open()
                self.assertTrue(pool.is_open)
                pool.close()
                pool.close()

        password_loader.assert_called_once_with("clearspend-synthetic", "clearspend_app")
        pool_factory.assert_called_once()
        pool_kwargs = pool_factory.call_args.kwargs
        self.assertEqual(pool_kwargs["min_size"], 1)
        self.assertEqual(pool_kwargs["max_size"], 4)
        self.assertEqual(pool_kwargs["timeout"], 15.0)
        self.assertFalse(pool_kwargs["open"])
        pool_instance.open.assert_called_once_with(wait=True, timeout=15.0)
        pool_instance.close.assert_called_once_with()

    def test_connection_adapter_translates_neutral_bindings(self) -> None:
        connection = Mock()
        adapter = PostgreSQLConnection(connection)

        adapter.execute(
            "SELECT * FROM synthetic_items WHERE first_value=? AND second_value=?",
            (7, "synthetic"),
        )
        adapter.execute("SELECT TRUE AS synthetic_value")

        self.assertEqual(
            connection.execute.call_args_list[0].args,
            (
                "SELECT * FROM synthetic_items WHERE first_value=%s AND second_value=%s",
                (7, "synthetic"),
            ),
        )
        self.assertEqual(
            connection.execute.call_args_list[1].args,
            ("SELECT TRUE AS synthetic_value",),
        )

        composed = sql.SQL("SELECT {} AS synthetic_value").format(sql.Literal(17))
        adapter.execute(composed)
        self.assertIs(connection.execute.call_args_list[2].args[0], composed)

        cursor = connection.cursor.return_value
        adapter.executemany(
            "INSERT INTO synthetic_items(first_value,second_value) VALUES(?,?)",
            [(1, "first"), (2, "second")],
        )
        cursor.executemany.assert_called_once_with(
            "INSERT INTO synthetic_items(first_value,second_value) VALUES(%s,%s)",
            [(1, "first"), (2, "second")],
        )
        cursor.close.assert_called_once_with()

    def test_failed_pool_startup_closes_partial_pool(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            certificate = Path(directory) / "ca.crt"
            certificate.touch()
            pool_instance = Mock()
            pool_instance.open.side_effect = RuntimeError("synthetic connection failure")
            with patch(
                "clearspend.database.postgresql.ConnectionPool",
                return_value=pool_instance,
            ):
                pool = PostgreSQLPool(
                    self.settings(certificate),
                    password_loader=Mock(return_value="synthetic-secret"),
                )
                with self.assertRaisesRegex(DatabaseUnavailableError, "unavailable"):
                    pool.open()

        self.assertFalse(pool.is_open)
        pool_instance.close.assert_called_once_with()

    def test_connection_requires_open_pool_and_maps_acquisition_timeout(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            certificate = Path(directory) / "ca.crt"
            certificate.touch()
            pool = PostgreSQLPool(
                self.settings(certificate),
                password_loader=Mock(return_value="synthetic-secret"),
            )
            with self.assertRaisesRegex(DatabaseUnavailableError, "not open"):
                with pool.connection():
                    self.fail("an unopened pool must not yield a connection")

            pool_instance = Mock()
            pool_instance.connection.side_effect = PoolTimeout("synthetic timeout")
            with patch(
                "clearspend.database.postgresql.ConnectionPool",
                return_value=pool_instance,
            ):
                pool.open()
                with self.assertRaisesRegex(DatabaseBusyError, "pool is busy"):
                    with pool.connection():
                        self.fail("a timed-out pool must not yield a connection")
                pool.close()

        pool_instance.connection.assert_called_once_with(timeout=15.0)


if __name__ == "__main__":
    unittest.main()
