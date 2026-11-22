from __future__ import annotations

import io
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, call, patch

from clearspend.admin import _restore, _runtime_status, main
from clearspend.database.postgresql_backup import PostgreSQLBackupError
from clearspend.database.postgresql_migration_runner import PostgreSQLMigrationError


class PostgreSQLAdminCommandTests(unittest.TestCase):
    def test_commands_dispatch_their_documented_arguments(self) -> None:
        cases = (
            ("_status", ["status", "--admin-config", "admin.json"], (Path("admin.json"),)),
            (
                "_runtime_status",
                ["runtime-status", "--runtime-config", "runtime.json"],
                (Path("runtime.json"),),
            ),
            (
                "_provision",
                [
                    "provision", "--admin-config", "admin.json",
                    "--runtime-config", "runtime.json",
                ],
                (Path("admin.json"), Path("runtime.json")),
            ),
            ("_migrate", ["migrate", "--admin-config", "admin.json"], (Path("admin.json"),)),
            (
                "_backup",
                ["backup", "--runtime-config", "runtime.json", "--label", "manual"],
                (Path("runtime.json"), "manual"),
            ),
            (
                "_verify_backup",
                [
                    "verify-backup", "--runtime-config", "runtime.json",
                    "--archive", "backup.dump.enc",
                ],
                (Path("runtime.json"), Path("backup.dump.enc")),
            ),
            (
                "_restore",
                [
                    "restore", "--admin-config", "admin.json",
                    "--runtime-config", "runtime.json",
                    "--archive", "backup.dump.enc",
                ],
                (
                    Path("admin.json"),
                    Path("runtime.json"),
                    Path("backup.dump.enc"),
                ),
            ),
        )
        for function, arguments, expected in cases:
            with self.subTest(command=arguments[0]), patch(
                f"clearspend.admin.{function}"
            ) as operation:
                self.assertEqual(main(arguments), 0)
                operation.assert_called_once_with(*expected)

    def test_known_failure_is_concise_and_returns_nonzero(self) -> None:
        error_output = io.StringIO()
        with patch(
            "clearspend.admin._status",
            side_effect=PostgreSQLBackupError("synthetic safe failure"),
        ), redirect_stderr(error_output):
            result = main(["status", "--admin-config", "admin.json"])

        self.assertEqual(result, 1)
        self.assertEqual(
            error_output.getvalue().strip(),
            "ClearSpend admin error: synthetic safe failure",
        )

    def test_runtime_status_rejects_schema_that_is_not_current(self) -> None:
        configuration = SimpleNamespace(database=SimpleNamespace())
        pool = Mock()
        with patch(
            "clearspend.admin.load_postgresql_runtime_configuration",
            return_value=configuration,
        ), patch("clearspend.admin.PostgreSQLPool", return_value=pool), patch(
            "clearspend.admin.inspect_postgresql_schema",
            return_value=SimpleNamespace(state="versioned", version=4),
        ):
            with self.assertRaisesRegex(PostgreSQLMigrationError, "expected version 5"):
                _runtime_status(Path("runtime.json"))

        self.assertEqual(pool.method_calls, [call.open(), call.close()])

    def test_restore_bootstraps_role_before_restore_then_reapplies_security(self) -> None:
        runtime = SimpleNamespace(
            backup=SimpleNamespace(
                encryption_keychain_service="synthetic-backup",
                encryption_keychain_account="archive",
                psql_path=Path("psql"),
                pg_restore_path=Path("pg_restore"),
                openssl_path=Path("openssl"),
            )
        )
        pool = Mock()
        order: list[str] = []
        statuses = iter(
            (
                SimpleNamespace(state="unprovisioned", version=0),
                SimpleNamespace(state="versioned", version=5),
            )
        )
        with patch(
            "clearspend.admin._runtime_password",
            return_value=(runtime, "synthetic-runtime-password"),
        ), patch(
            "clearspend.admin.load_postgresql_admin_configuration",
            return_value=SimpleNamespace(),
        ), patch("clearspend.admin.PostgreSQLPool", return_value=pool), patch(
            "clearspend.admin.inspect_postgresql_schema",
            side_effect=lambda selected: next(statuses),
        ), patch(
            "clearspend.admin.bootstrap_postgresql_runtime_role",
            side_effect=lambda *args: order.append("bootstrap"),
        ) as bootstrap, patch(
            "clearspend.admin.restore_verified_postgresql_backup",
            side_effect=lambda *args, **kwargs: order.append("restore"),
        ) as restore, patch(
            "clearspend.admin.provision_postgresql",
            side_effect=lambda *args: order.append("provision"),
        ) as provision, redirect_stdout(io.StringIO()):
            _restore(
                Path("admin.json"),
                Path("runtime.json"),
                Path("archive.dump.enc"),
            )

        self.assertEqual(order, ["bootstrap", "restore", "provision"])
        self.assertEqual(bootstrap.call_args.args[1], "synthetic-runtime-password")
        self.assertEqual(restore.call_args.kwargs["psql_path"], Path("psql"))
        self.assertEqual(provision.call_args.args[1], "synthetic-runtime-password")
        self.assertEqual(pool.method_calls, [call.open(), call.close()])


if __name__ == "__main__":
    unittest.main()
