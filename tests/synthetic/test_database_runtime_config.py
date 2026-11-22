from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from clearspend.database.runtime_config import (
    RuntimeConfigurationError,
    load_postgresql_runtime_configuration,
)


class PostgreSQLRuntimeConfigurationTests(unittest.TestCase):
    def values(self) -> dict:
        return {
            "backend": "postgresql",
            "host": "synthetic.pooler.invalid",
            "port": 5432,
            "database": "postgres",
            "user": "clearspend_app",
            "ssl_root_certificate": "certificates/ca.crt",
            "keychain_service": "synthetic-runtime-service",
            "keychain_account": "clearspend_app",
            "local_state_directory": "state",
            "backup_directory": "backups/postgresql",
            "backup_encryption_keychain_service": "synthetic-backup-service",
            "backup_encryption_keychain_account": "archive",
        }

    def test_complete_configuration_resolves_local_paths_without_passwords(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / "runtime.json"
            path.write_text(json.dumps(self.values()), encoding="utf-8")

            configuration = load_postgresql_runtime_configuration(path)

        self.assertEqual(configuration.database.host, "synthetic.pooler.invalid")
        self.assertEqual(configuration.database.user, "clearspend_app")
        self.assertEqual(
            configuration.database.ssl_root_certificate,
            (root / "certificates" / "ca.crt").resolve(),
        )
        self.assertEqual(
            configuration.local_state_directory,
            (root / "state").resolve(),
        )
        self.assertEqual(
            configuration.backup.directory,
            (root / "backups" / "postgresql").resolve(),
        )
        self.assertEqual(configuration.backup.psql_path, Path("psql"))

    def test_missing_unknown_and_wrong_backend_configuration_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / "runtime.json"
            values = self.values()
            values.pop("host")
            path.write_text(json.dumps(values), encoding="utf-8")
            with self.assertRaisesRegex(RuntimeConfigurationError, "missing required"):
                load_postgresql_runtime_configuration(path)

            values = self.values()
            values["password"] = "must-not-be-configurable"
            path.write_text(json.dumps(values), encoding="utf-8")
            with self.assertRaisesRegex(RuntimeConfigurationError, "unknown fields"):
                load_postgresql_runtime_configuration(path)

            values = self.values()
            values["backend"] = "sqlite"
            path.write_text(json.dumps(values), encoding="utf-8")
            with self.assertRaisesRegex(RuntimeConfigurationError, "postgresql backend"):
                load_postgresql_runtime_configuration(path)

    def test_configuration_file_must_be_valid_json_object(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "runtime.json"
            path.write_text("[]", encoding="utf-8")
            with self.assertRaisesRegex(RuntimeConfigurationError, "must be an object"):
                load_postgresql_runtime_configuration(path)

            path.write_text("not-json", encoding="utf-8")
            with self.assertRaisesRegex(RuntimeConfigurationError, "could not be read"):
                load_postgresql_runtime_configuration(path)

    def test_invalid_connection_values_fail_as_configuration_errors(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "runtime.json"
            values = self.values()
            values["port"] = "not-a-port"
            path.write_text(json.dumps(values), encoding="utf-8")

            with self.assertRaisesRegex(RuntimeConfigurationError, "values are invalid"):
                load_postgresql_runtime_configuration(path)

    def test_tracked_runtime_template_matches_the_loader_contract(self) -> None:
        template = (
            Path(__file__).resolve().parents[2]
            / "config"
            / "postgresql-runtime.example.json"
        )

        configuration = load_postgresql_runtime_configuration(template)

        self.assertIn("example-project-ref", configuration.database.user)
        self.assertEqual(configuration.backup.psql_path, Path("psql"))
        self.assertNotIn("password", template.read_text(encoding="utf-8").casefold())


if __name__ == "__main__":
    unittest.main()
