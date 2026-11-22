from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from clearspend.database.admin_config import (
    AdminConfigurationError,
    load_postgresql_admin_configuration,
)


class PostgreSQLAdminConfigurationTests(unittest.TestCase):
    def values(self) -> dict:
        return {
            "backend": "postgresql",
            "expected_region": "eu-central-1",
            "host": "aws-0-eu-central-1.pooler.supabase.com",
            "port": 5432,
            "database": "postgres",
            "user": "postgres.synthetic-project",
            "ssl_root_certificate": "certificates/ca.crt",
            "keychain_service": "synthetic-admin-service",
            "keychain_account": "postgres",
        }

    def test_complete_admin_configuration_contains_no_password(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / "admin.json"
            path.write_text(json.dumps(self.values()), encoding="utf-8")

            settings = load_postgresql_admin_configuration(path)

        self.assertEqual(settings.user, "postgres.synthetic-project")
        self.assertEqual(settings.pool_max_size, 2)
        self.assertEqual(settings.statement_timeout_milliseconds, 30_000)
        self.assertEqual(
            settings.ssl_root_certificate,
            (root / "certificates" / "ca.crt").resolve(),
        )

    def test_admin_configuration_rejects_missing_unknown_and_invalid_values(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "admin.json"
            values = self.values()
            values.pop("host")
            path.write_text(json.dumps(values), encoding="utf-8")
            with self.assertRaisesRegex(AdminConfigurationError, "missing required"):
                load_postgresql_admin_configuration(path)

            values = self.values()
            values["password"] = "must-not-be-configurable"
            path.write_text(json.dumps(values), encoding="utf-8")
            with self.assertRaisesRegex(AdminConfigurationError, "unknown fields"):
                load_postgresql_admin_configuration(path)

            values = self.values()
            values["port"] = "invalid"
            path.write_text(json.dumps(values), encoding="utf-8")
            with self.assertRaisesRegex(AdminConfigurationError, "values are invalid"):
                load_postgresql_admin_configuration(path)

    def test_admin_pooler_region_must_match_expected_region(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "admin.json"
            values = self.values()
            values["host"] = "aws-0-ap-southeast-2.pooler.supabase.com"
            path.write_text(json.dumps(values), encoding="utf-8")

            with self.assertRaisesRegex(
                AdminConfigurationError,
                "host region does not match expected_region",
            ):
                load_postgresql_admin_configuration(path)

    def test_tracked_admin_template_matches_the_loader_contract(self) -> None:
        template = (
            Path(__file__).resolve().parents[2]
            / "config"
            / "postgresql-admin.example.json"
        )

        settings = load_postgresql_admin_configuration(template)

        self.assertIn("example-project-ref", settings.user)
        self.assertNotIn("password", template.read_text(encoding="utf-8").casefold())


if __name__ == "__main__":
    unittest.main()
