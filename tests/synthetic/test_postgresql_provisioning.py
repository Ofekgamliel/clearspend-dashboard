from __future__ import annotations

import base64
import hashlib
import hmac
import unittest
from contextlib import contextmanager
from unittest.mock import Mock, patch

from psycopg.sql import Composed

from clearspend.database.postgresql_provisioning import (
    PostgreSQLProvisioningError,
    build_scram_sha_256_verifier,
    provision_postgresql,
)


class Result:
    def __init__(self, rows):
        self.rows = list(rows)

    def fetchone(self):
        return self.rows[0] if self.rows else None

    def fetchall(self):
        return self.rows


class ProvisioningConnection:
    def __init__(self, *, current_role="postgres", role_exists=False) -> None:
        self.current_role = current_role
        self.role_exists = role_exists
        self.executed = []

    def execute(self, statement, parameters=None):
        self.executed.append((statement, parameters))
        if isinstance(statement, Composed):
            return Result([])
        if "current_user AS current_role" in statement:
            return Result([{"current_role": self.current_role}])
        if "SELECT EXISTS" in statement and "WHERE rolname=?" in statement:
            return Result([{"present": self.role_exists}])
        if statement.lstrip().startswith(("CREATE", "REVOKE", "GRANT", "ALTER")):
            return Result([])
        if "rolcanlogin,rolsuper" in statement:
            return Result(
                [
                    {
                        "rolcanlogin": True,
                        "rolsuper": False,
                        "rolinherit": False,
                        "rolcreaterole": False,
                        "rolcreatedb": False,
                        "rolreplication": False,
                        "rolbypassrls": False,
                    }
                ]
            )
        if "information_schema.schemata" in statement:
            return Result([{"schema_owner": "postgres"}])
        if "has_schema_privilege" in statement:
            return Result([{"can_use": True, "can_create": False}])
        if "aclexplode" in statement:
            return Result([])
        if "pg_catalog.pg_auth_members" in statement:
            return Result([])
        if "pg_catalog.pg_db_role_setting" in statement:
            return Result([{"configured": True}])
        raise AssertionError(f"Unexpected provisioning SQL: {statement}")


@contextmanager
def yielding(value):
    yield value


class PostgreSQLProvisioningTests(unittest.TestCase):
    def test_scram_verifier_contains_valid_keys_without_plaintext(self) -> None:
        password = "synthetic-password-value"
        salt = bytes(range(16))
        verifier = build_scram_sha_256_verifier(
            password,
            salt_factory=lambda size: salt,
        )

        mechanism, details = verifier.split("$", 1)
        iteration_and_salt, keys = details.split("$")
        iterations, encoded_salt = iteration_and_salt.split(":")
        encoded_stored_key, encoded_server_key = keys.split(":")
        salted_password = hashlib.pbkdf2_hmac(
            "sha256", password.encode(), salt, int(iterations)
        )
        client_key = hmac.new(salted_password, b"Client Key", hashlib.sha256).digest()

        self.assertEqual(mechanism, "SCRAM-SHA-256")
        self.assertEqual(base64.b64decode(encoded_salt), salt)
        self.assertEqual(
            base64.b64decode(encoded_stored_key),
            hashlib.sha256(client_key).digest(),
        )
        self.assertEqual(
            base64.b64decode(encoded_server_key),
            hmac.new(salted_password, b"Server Key", hashlib.sha256).digest(),
        )
        self.assertNotIn(password, verifier)

    def test_short_runtime_password_is_rejected_before_database_access(self) -> None:
        with self.assertRaisesRegex(ValueError, "at least 20"):
            build_scram_sha_256_verifier("too-short")

    def test_provisioning_creates_role_and_private_schema(self) -> None:
        connection = ProvisioningConnection()
        with patch(
            "clearspend.database.postgresql_provisioning.database_transaction",
            return_value=yielding(connection),
        ):
            result = provision_postgresql(
                Mock(),
                "synthetic-password-value",
                salt_factory=lambda size: bytes(range(size)),
            )

        self.assertTrue(result.role_created)
        self.assertEqual(result.schema, "clearspend")
        self.assertEqual(result.runtime_role, "clearspend_app")
        composed = [statement for statement, _ in connection.executed if isinstance(statement, Composed)]
        self.assertEqual(len(composed), 1)
        plain_sql = "\n".join(
            statement for statement, _ in connection.executed if isinstance(statement, str)
        )
        self.assertIn("REVOKE ALL PRIVILEGES ON SCHEMA clearspend", plain_sql)
        self.assertIn("GRANT USAGE ON SCHEMA clearspend TO clearspend_app", plain_sql)
        self.assertIn("SET search_path TO clearspend, pg_catalog", plain_sql)

    def test_existing_role_is_verified_without_replacing_its_password(self) -> None:
        connection = ProvisioningConnection(role_exists=True)
        with patch(
            "clearspend.database.postgresql_provisioning.database_transaction",
            return_value=yielding(connection),
        ):
            result = provision_postgresql(Mock(), "synthetic-password-value")

        self.assertFalse(result.role_created)
        self.assertFalse(
            any(isinstance(statement, Composed) for statement, _ in connection.executed)
        )

    def test_non_admin_connection_is_rejected_before_ddl(self) -> None:
        connection = ProvisioningConnection(current_role="clearspend_app")
        with patch(
            "clearspend.database.postgresql_provisioning.database_transaction",
            return_value=yielding(connection),
        ):
            with self.assertRaisesRegex(PostgreSQLProvisioningError, "postgres"):
                provision_postgresql(Mock(), "synthetic-password-value")

        self.assertEqual(len(connection.executed), 1)


if __name__ == "__main__":
    unittest.main()
