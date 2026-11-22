from __future__ import annotations

import argparse
import sys
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator, Sequence

from clearspend.database.admin_config import (
    AdminConfigurationError,
    load_postgresql_admin_configuration,
)
from clearspend.database.errors import DatabaseUnavailableError
from clearspend.database.keychain import KeychainPasswordError, load_keychain_password
from clearspend.database.postgresql import PostgreSQLPool
from clearspend.database.postgresql_backup import (
    PostgreSQLBackupError,
    create_verified_postgresql_backup,
    restore_verified_postgresql_backup,
    verify_postgresql_backup,
)
from clearspend.database.postgresql_migration_runner import (
    PostgreSQLMigrationError,
    inspect_postgresql_schema,
    migrate_postgresql,
)
from clearspend.database.postgresql_migrations import CURRENT_POSTGRESQL_SCHEMA_VERSION
from clearspend.database.postgresql_provisioning import (
    PostgreSQLProvisioningError,
    bootstrap_postgresql_runtime_role,
    provision_postgresql,
)
from clearspend.database.runtime_config import (
    PostgreSQLRuntimeConfiguration,
    RuntimeConfigurationError,
    load_postgresql_runtime_configuration,
)


KNOWN_ADMIN_ERRORS = (
    AdminConfigurationError,
    DatabaseUnavailableError,
    KeychainPasswordError,
    PostgreSQLBackupError,
    PostgreSQLMigrationError,
    PostgreSQLProvisioningError,
    RuntimeConfigurationError,
    ValueError,
)


@contextmanager
def _open_admin_pool(config_path: Path) -> Iterator[PostgreSQLPool]:
    pool = PostgreSQLPool(load_postgresql_admin_configuration(config_path.resolve()))
    pool.open()
    try:
        yield pool
    finally:
        pool.close()


def _runtime_password(
    config_path: Path,
) -> tuple[PostgreSQLRuntimeConfiguration, str]:
    configuration = load_postgresql_runtime_configuration(config_path.resolve())
    password = load_keychain_password(
        configuration.database.keychain_service,
        configuration.database.keychain_account,
    )
    return configuration, password


def _status(admin_config: Path) -> None:
    with _open_admin_pool(admin_config) as pool:
        status = inspect_postgresql_schema(pool)
    details = "; ".join(status.problems) if status.problems else "no problems"
    print(
        f"PostgreSQL schema: {status.state}; version {status.version}; {details}"
    )


def _runtime_status(runtime_config: Path) -> None:
    configuration = load_postgresql_runtime_configuration(runtime_config.resolve())
    pool = PostgreSQLPool(configuration.database)
    pool.open()
    try:
        status = inspect_postgresql_schema(pool)
    finally:
        pool.close()
    if (
        status.state != "versioned"
        or status.version != CURRENT_POSTGRESQL_SCHEMA_VERSION
    ):
        raise PostgreSQLMigrationError(
            "PostgreSQL runtime schema is not current; "
            f"found {status.state} version {status.version}, expected version "
            f"{CURRENT_POSTGRESQL_SCHEMA_VERSION}"
        )
    details = "; ".join(status.problems) if status.problems else "no problems"
    print(
        f"PostgreSQL runtime: {status.state}; version {status.version}; {details}"
    )


def _provision(admin_config: Path, runtime_config: Path) -> None:
    _, runtime_password = _runtime_password(runtime_config)
    with _open_admin_pool(admin_config) as pool:
        result = provision_postgresql(pool, runtime_password)
    role_status = "created" if result.role_created else "verified"
    print(
        f"Provisioned schema {result.schema}; runtime role "
        f"{result.runtime_role} {role_status}"
    )


def _migrate(admin_config: Path) -> None:
    with _open_admin_pool(admin_config) as pool:
        result = migrate_postgresql(pool)
    applied = ",".join(str(version) for version in result.applied_versions) or "none"
    print(
        f"PostgreSQL migrations: {result.starting_version} -> "
        f"{result.ending_version}; applied {applied}"
    )


def _backup(runtime_config: Path, label: str) -> None:
    configuration = load_postgresql_runtime_configuration(runtime_config.resolve())
    backup = configuration.backup
    archive = create_verified_postgresql_backup(
        configuration.database,
        backup.directory,
        label,
        encryption_keychain_service=backup.encryption_keychain_service,
        encryption_keychain_account=backup.encryption_keychain_account,
        pg_dump_path=backup.pg_dump_path,
        pg_restore_path=backup.pg_restore_path,
        openssl_path=backup.openssl_path,
    )
    print(f"PostgreSQL backup created and verified: {archive}")


def _verify_backup(runtime_config: Path, archive: Path) -> None:
    configuration = load_postgresql_runtime_configuration(runtime_config.resolve())
    backup = configuration.backup
    verify_postgresql_backup(
        archive.resolve(),
        encryption_keychain_service=backup.encryption_keychain_service,
        encryption_keychain_account=backup.encryption_keychain_account,
        pg_restore_path=backup.pg_restore_path,
        openssl_path=backup.openssl_path,
    )
    print(f"PostgreSQL backup verified: {archive.name}")


def _restore(admin_config: Path, runtime_config: Path, archive: Path) -> None:
    configuration, runtime_password = _runtime_password(runtime_config)
    backup = configuration.backup
    admin_settings = load_postgresql_admin_configuration(admin_config.resolve())
    pool = PostgreSQLPool(admin_settings)
    pool.open()
    try:
        before = inspect_postgresql_schema(pool)
        if before.state != "unprovisioned":
            raise PostgreSQLBackupError(
                "PostgreSQL recovery target already contains the private schema"
            )
        bootstrap_postgresql_runtime_role(pool, runtime_password)
        try:
            restore_verified_postgresql_backup(
                archive.resolve(),
                admin_settings,
                encryption_keychain_service=backup.encryption_keychain_service,
                encryption_keychain_account=backup.encryption_keychain_account,
                psql_path=backup.psql_path,
                pg_restore_path=backup.pg_restore_path,
                openssl_path=backup.openssl_path,
            )
        except Exception as error:
            failed_state = inspect_postgresql_schema(pool)
            if failed_state.state == "unprovisioned":
                raise PostgreSQLBackupError(
                    "PostgreSQL restore failed before schema creation; the "
                    "schema-empty target can be retried"
                ) from error
            raise PostgreSQLBackupError(
                "PostgreSQL restore failed after changing the target; keep the "
                "server stopped and inspect the recovery environment"
            ) from error
        try:
            provision_postgresql(pool, runtime_password)
            after = inspect_postgresql_schema(pool)
            if (
                after.state != "versioned"
                or after.version != CURRENT_POSTGRESQL_SCHEMA_VERSION
            ):
                raise PostgreSQLBackupError(
                    "PostgreSQL recovery schema verification failed"
                )
        except Exception as error:
            raise PostgreSQLBackupError(
                "PostgreSQL backup was restored but security verification failed; "
                "keep the server stopped and complete provisioning"
            ) from error
    finally:
        pool.close()
    print(
        "PostgreSQL backup restored; runtime security verified; "
        f"schema version {after.version}"
    )


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Explicit administrative operations for ClearSpend PostgreSQL"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    status = subparsers.add_parser("status", help="inspect schema state without mutation")
    status.add_argument("--admin-config", type=Path, required=True)

    runtime_status = subparsers.add_parser(
        "runtime-status",
        help="validate restricted runtime connectivity without mutation",
    )
    runtime_status.add_argument("--runtime-config", type=Path, required=True)

    provision = subparsers.add_parser(
        "provision", help="create and verify the private schema and runtime role"
    )
    provision.add_argument("--admin-config", type=Path, required=True)
    provision.add_argument("--runtime-config", type=Path, required=True)

    migrate = subparsers.add_parser("migrate", help="apply and verify pending migrations")
    migrate.add_argument("--admin-config", type=Path, required=True)

    backup = subparsers.add_parser("backup", help="create a verified encrypted backup")
    backup.add_argument("--runtime-config", type=Path, required=True)
    backup.add_argument("--label", required=True)

    verify = subparsers.add_parser(
        "verify-backup", help="authenticate and inspect an encrypted backup"
    )
    verify.add_argument("--runtime-config", type=Path, required=True)
    verify.add_argument("--archive", type=Path, required=True)

    restore = subparsers.add_parser(
        "restore", help="restore into a schema-empty replacement environment"
    )
    restore.add_argument("--admin-config", type=Path, required=True)
    restore.add_argument("--runtime-config", type=Path, required=True)
    restore.add_argument("--archive", type=Path, required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        if args.command == "status":
            _status(args.admin_config)
        elif args.command == "runtime-status":
            _runtime_status(args.runtime_config)
        elif args.command == "provision":
            _provision(args.admin_config, args.runtime_config)
        elif args.command == "migrate":
            _migrate(args.admin_config)
        elif args.command == "backup":
            _backup(args.runtime_config, args.label)
        elif args.command == "verify-backup":
            _verify_backup(args.runtime_config, args.archive)
        elif args.command == "restore":
            _restore(args.admin_config, args.runtime_config, args.archive)
    except KNOWN_ADMIN_ERRORS as error:
        print(f"ClearSpend admin error: {error}", file=sys.stderr)
        return 1
    except Exception:
        print("ClearSpend admin error: unexpected operation failure", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
