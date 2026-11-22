from __future__ import annotations

import base64
import hashlib
import hmac
import os
from dataclasses import dataclass
from typing import Any, Callable

from psycopg import sql

from clearspend.database.connection import database_transaction
from clearspend.database.postgresql import PostgreSQLPool


RUNTIME_ROLE = "clearspend_app"
PRIVATE_SCHEMA = "clearspend"
API_ROLES = ("PUBLIC", "anon", "authenticated", "service_role")
SCRAM_ITERATIONS = 4096
SaltFactory = Callable[[int], bytes]


class PostgreSQLProvisioningError(RuntimeError):
    """Raised when the private PostgreSQL boundary cannot be provisioned safely."""


@dataclass(frozen=True)
class PostgreSQLProvisioningResult:
    role_created: bool
    schema: str
    runtime_role: str


def build_scram_sha_256_verifier(
    password: str,
    *,
    salt_factory: SaltFactory = os.urandom,
) -> str:
    """Build a PostgreSQL SCRAM verifier without putting plaintext in SQL."""
    if len(password) < 20:
        raise ValueError("PostgreSQL runtime password must contain at least 20 characters")
    salt = salt_factory(16)
    if len(salt) != 16:
        raise ValueError("SCRAM salt factory must return exactly 16 bytes")
    salted_password = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt,
        SCRAM_ITERATIONS,
    )
    client_key = hmac.new(salted_password, b"Client Key", hashlib.sha256).digest()
    stored_key = hashlib.sha256(client_key).digest()
    server_key = hmac.new(salted_password, b"Server Key", hashlib.sha256).digest()
    encoded_salt = base64.b64encode(salt).decode("ascii")
    encoded_stored_key = base64.b64encode(stored_key).decode("ascii")
    encoded_server_key = base64.b64encode(server_key).decode("ascii")
    return (
        f"SCRAM-SHA-256${SCRAM_ITERATIONS}:{encoded_salt}"
        f"${encoded_stored_key}:{encoded_server_key}"
    )


def _verify_private_boundary(connection: Any) -> list[str]:
    problems: list[str] = []
    role = connection.execute(
        """SELECT rolcanlogin,rolsuper,rolinherit,rolcreaterole,rolcreatedb,
        rolreplication,rolbypassrls
        FROM pg_catalog.pg_roles WHERE rolname=?""",
        (RUNTIME_ROLE,),
    ).fetchone()
    if role is None:
        problems.append("Runtime role clearspend_app does not exist")
    elif not (
        role["rolcanlogin"]
        and not role["rolsuper"]
        and not role["rolinherit"]
        and not role["rolcreaterole"]
        and not role["rolcreatedb"]
        and not role["rolreplication"]
        and not role["rolbypassrls"]
    ):
        problems.append("Runtime role has unsafe attributes")

    schema = connection.execute(
        """SELECT schema_owner FROM information_schema.schemata
        WHERE schema_name=?""",
        (PRIVATE_SCHEMA,),
    ).fetchone()
    if schema is None:
        problems.append("Private schema clearspend does not exist")
    elif schema["schema_owner"] != "postgres":
        problems.append("Private schema is not owned by postgres")

    runtime_access = connection.execute(
        """SELECT has_schema_privilege(?, ?, 'USAGE') AS can_use,
        has_schema_privilege(?, ?, 'CREATE') AS can_create""",
        (RUNTIME_ROLE, PRIVATE_SCHEMA, RUNTIME_ROLE, PRIVATE_SCHEMA),
    ).fetchone()
    if not runtime_access["can_use"] or runtime_access["can_create"]:
        problems.append("Runtime role has incorrect private-schema privileges")

    denied_access = connection.execute(
        """SELECT COALESCE(grantee.rolname,'PUBLIC') AS grantee,
        access.privilege_type
        FROM pg_catalog.pg_namespace namespace
        CROSS JOIN LATERAL pg_catalog.aclexplode(
          COALESCE(namespace.nspacl,
            pg_catalog.acldefault('n',namespace.nspowner))
        ) access
        LEFT JOIN pg_catalog.pg_roles grantee ON grantee.oid=access.grantee
        WHERE namespace.nspname=? AND (
          access.grantee=0
          OR grantee.rolname IN ('anon','authenticated','service_role')
        )""",
        (PRIVATE_SCHEMA,),
    ).fetchall()
    if denied_access:
        problems.append("API roles or PUBLIC can use the private schema")

    memberships = connection.execute(
        """SELECT parent.rolname FROM pg_catalog.pg_auth_members membership
        JOIN pg_catalog.pg_roles member ON member.oid=membership.member
        JOIN pg_catalog.pg_roles parent ON parent.oid=membership.roleid
        WHERE member.rolname=?""",
        (RUNTIME_ROLE,),
    ).fetchall()
    if memberships:
        problems.append("Runtime role inherits another database role")

    search_path = connection.execute(
        """SELECT EXISTS(
          SELECT 1 FROM pg_catalog.pg_db_role_setting setting
          JOIN pg_catalog.pg_roles role ON role.oid=setting.setrole
          WHERE role.rolname=?
          AND 'search_path=clearspend, pg_catalog'=ANY(setting.setconfig)
        ) AS configured""",
        (RUNTIME_ROLE,),
    ).fetchone()
    if not search_path["configured"]:
        problems.append("Runtime role search_path is not restricted")
    return problems


def provision_postgresql(
    pool: PostgreSQLPool,
    runtime_password: str,
    *,
    salt_factory: SaltFactory = os.urandom,
) -> PostgreSQLProvisioningResult:
    verifier = build_scram_sha_256_verifier(
        runtime_password,
        salt_factory=salt_factory,
    )
    with database_transaction(pool) as connection:
        current_role = connection.execute(
            "SELECT current_user AS current_role"
        ).fetchone()["current_role"]
        if current_role != "postgres":
            raise PostgreSQLProvisioningError(
                "PostgreSQL provisioning requires the postgres administrative role"
            )
        role_exists = connection.execute(
            "SELECT EXISTS(SELECT 1 FROM pg_catalog.pg_roles WHERE rolname=?) AS present",
            (RUNTIME_ROLE,),
        ).fetchone()["present"]
        if not role_exists:
            connection.execute(
                sql.SQL(
                    """CREATE ROLE {} LOGIN PASSWORD {} NOSUPERUSER NOCREATEDB
                    NOCREATEROLE NOINHERIT NOREPLICATION NOBYPASSRLS"""
                ).format(sql.Identifier(RUNTIME_ROLE), sql.Literal(verifier))
            )
        connection.execute(
            "CREATE SCHEMA IF NOT EXISTS clearspend AUTHORIZATION postgres"
        )
        connection.execute(
            """REVOKE ALL PRIVILEGES ON SCHEMA clearspend
            FROM PUBLIC, anon, authenticated, service_role"""
        )
        connection.execute("GRANT USAGE ON SCHEMA clearspend TO clearspend_app")
        connection.execute(
            "ALTER ROLE clearspend_app SET search_path TO clearspend, pg_catalog"
        )
        problems = _verify_private_boundary(connection)
        if problems:
            raise PostgreSQLProvisioningError(
                "PostgreSQL provisioning verification failed: " + "; ".join(problems)
            )
    return PostgreSQLProvisioningResult(
        role_created=not role_exists,
        schema=PRIVATE_SCHEMA,
        runtime_role=RUNTIME_ROLE,
    )
