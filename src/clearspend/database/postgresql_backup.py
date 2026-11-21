from __future__ import annotations

import os
import re
import subprocess
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Mapping, Sequence, Tuple

from clearspend.database.keychain import load_keychain_password
from clearspend.database.settings import PostgreSQLSettings


EXPECTED_CLEARSPEND_TABLES = frozenset(
    {
        "event_transactions",
        "events",
        "import_coverage",
        "import_transactions",
        "imports",
        "income_entries",
        "income_imports",
        "merchant_display_mappings",
        "merchant_mappings",
        "observation_reviews",
        "recurring_profile_members",
        "recurring_profiles",
        "schema_migrations",
        "transaction_category_overrides",
        "transaction_spending_adjustments",
        "transactions",
    }
)

PasswordLoader = Callable[[str, str], str]
PipelineRunner = Callable[
    [Sequence[str], Mapping[str, str], Sequence[str], Mapping[str, str]],
    bytes,
]
CommandRunner = Callable[[Sequence[str], Mapping[str, str]], bytes]


class PostgreSQLBackupError(RuntimeError):
    """Raised when an encrypted PostgreSQL backup cannot be created or verified."""


@dataclass(frozen=True)
class PostgreSQLBackupConfiguration:
    directory: Path
    encryption_keychain_service: str
    encryption_keychain_account: str
    pg_dump_path: Path = Path("pg_dump")
    pg_restore_path: Path = Path("pg_restore")
    openssl_path: Path = Path("openssl")

    def __post_init__(self) -> None:
        if not str(self.encryption_keychain_service).strip():
            raise ValueError("PostgreSQL backup Keychain service is required")
        if not str(self.encryption_keychain_account).strip():
            raise ValueError("PostgreSQL backup Keychain account is required")


def _run_command(command: Sequence[str], environment: Mapping[str, str]) -> bytes:
    try:
        result = subprocess.run(
            list(command),
            env=dict(environment),
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            check=False,
        )
    except OSError as error:
        raise PostgreSQLBackupError("PostgreSQL recovery tooling is unavailable") from error
    if result.returncode != 0:
        raise PostgreSQLBackupError("PostgreSQL recovery verification failed")
    return result.stdout


def _run_pipeline(
    first_command: Sequence[str],
    first_environment: Mapping[str, str],
    second_command: Sequence[str],
    second_environment: Mapping[str, str],
) -> bytes:
    """Run a two-process binary pipeline without exposing diagnostic contents."""
    if len(second_command) == 2 and second_command[-1] == "--list":
        return _run_archive_listing_pipeline(
            first_command,
            first_environment,
            second_command,
            second_environment,
        )
    try:
        first = subprocess.Popen(
            list(first_command),
            env=dict(first_environment),
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
        )
        if first.stdout is None:
            first.kill()
            first.wait()
            raise PostgreSQLBackupError("PostgreSQL backup pipeline could not start")
        try:
            second = subprocess.Popen(
                list(second_command),
                env=dict(second_environment),
                stdin=first.stdout,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
            )
        except BaseException:
            first.stdout.close()
            first.kill()
            first.wait()
            raise
        first.stdout.close()
        output, _ = second.communicate()
        first_return_code = first.wait()
    except OSError as error:
        raise PostgreSQLBackupError("PostgreSQL backup tooling is unavailable") from error

    if first_return_code != 0 and second.returncode != 0:
        raise PostgreSQLBackupError("PostgreSQL backup pipeline both stages failed")
    if first_return_code != 0:
        raise PostgreSQLBackupError("PostgreSQL backup pipeline first stage failed")
    if second.returncode != 0:
        raise PostgreSQLBackupError("PostgreSQL backup pipeline second stage failed")
    return output


def _run_archive_listing_pipeline(
    decrypt_command: Sequence[str],
    decrypt_environment: Mapping[str, str],
    listing_command: Sequence[str],
    listing_environment: Mapping[str, str],
) -> bytes:
    """Fully decrypt in memory before listing so the consumer cannot close early."""
    try:
        decrypted = subprocess.run(
            list(decrypt_command),
            env=dict(decrypt_environment),
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            check=False,
        )
        if decrypted.returncode != 0:
            raise PostgreSQLBackupError(
                "PostgreSQL backup pipeline first stage failed"
            )
        listing = subprocess.run(
            list(listing_command),
            env=dict(listing_environment),
            input=decrypted.stdout,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            check=False,
        )
    except OSError as error:
        raise PostgreSQLBackupError("PostgreSQL backup tooling is unavailable") from error
    if listing.returncode != 0:
        raise PostgreSQLBackupError("PostgreSQL backup pipeline second stage failed")
    return listing.stdout


def _database_environment(settings: PostgreSQLSettings, password: str) -> dict[str, str]:
    environment = dict(os.environ)
    environment.pop("CLEARSPEND_BACKUP_PASSPHRASE", None)
    environment.update(
        {
            "PGPASSWORD": password,
            "PGSSLMODE": "verify-full",
            "PGSSLROOTCERT": str(settings.ssl_root_certificate),
        }
    )
    return environment


def _encryption_environment(passphrase: str) -> dict[str, str]:
    environment = dict(os.environ)
    environment.pop("PGPASSWORD", None)
    environment["CLEARSPEND_BACKUP_PASSPHRASE"] = passphrase
    return environment


def _pg_dump_command(executable: Path, settings: PostgreSQLSettings) -> Tuple[str, ...]:
    return (
        str(executable),
        f"--host={settings.host}",
        f"--port={settings.port}",
        f"--username={settings.user}",
        f"--dbname={settings.database}",
        "--schema=clearspend",
        "--format=custom",
        "--no-owner",
        "--no-password",
    )


def _encrypt_command(executable: Path, destination: Path) -> Tuple[str, ...]:
    return (
        str(executable),
        "enc",
        "-aes-256-cbc",
        "-salt",
        "-pbkdf2",
        "-iter",
        "200000",
        "-pass",
        "env:CLEARSPEND_BACKUP_PASSPHRASE",
        "-out",
        str(destination),
    )


def _decrypt_command(executable: Path, source: Path) -> Tuple[str, ...]:
    return (
        str(executable),
        "enc",
        "-d",
        "-aes-256-cbc",
        "-pbkdf2",
        "-iter",
        "200000",
        "-pass",
        "env:CLEARSPEND_BACKUP_PASSPHRASE",
        "-in",
        str(source),
    )


def _pg_restore_list_command(executable: Path) -> Tuple[str, ...]:
    return (str(executable), "--list")


def _psql_command(
    executable: Path, settings: PostgreSQLSettings, query: str
) -> Tuple[str, ...]:
    return (
        str(executable),
        f"--host={settings.host}",
        f"--port={settings.port}",
        f"--username={settings.user}",
        f"--dbname={settings.database}",
        "--no-password",
        "--tuples-only",
        "--no-align",
        "--set=ON_ERROR_STOP=1",
        f"--command={query}",
    )


def _pg_restore_command(
    executable: Path, settings: PostgreSQLSettings
) -> Tuple[str, ...]:
    return (
        str(executable),
        f"--host={settings.host}",
        f"--port={settings.port}",
        f"--username={settings.user}",
        f"--dbname={settings.database}",
        "--no-password",
        "--no-owner",
        "--exit-on-error",
        "--single-transaction",
    )


def _listed_tables(listing: str) -> frozenset[str]:
    return frozenset(
        match.group(1)
        for match in re.finditer(r"\sTABLE clearspend ([^\s;]+)", listing)
    )


def create_verified_postgresql_backup(
    settings: PostgreSQLSettings,
    backup_directory: Path,
    label: str,
    *,
    encryption_keychain_service: str,
    encryption_keychain_account: str,
    pg_dump_path: Path = Path("pg_dump"),
    pg_restore_path: Path = Path("pg_restore"),
    openssl_path: Path = Path("openssl"),
    password_loader: PasswordLoader = load_keychain_password,
    pipeline_runner: PipelineRunner = _run_pipeline,
) -> Path:
    """Stream, encrypt, and structurally verify a ClearSpend logical backup."""
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]*", label):
        raise PostgreSQLBackupError("PostgreSQL backup label is invalid")
    if not settings.ssl_root_certificate.is_file():
        raise PostgreSQLBackupError("PostgreSQL root certificate does not exist")

    database_password = password_loader(settings.keychain_service, settings.keychain_account)
    encryption_passphrase = password_loader(
        encryption_keychain_service,
        encryption_keychain_account,
    )
    if database_password == encryption_passphrase:
        raise PostgreSQLBackupError(
            "PostgreSQL and backup-encryption credentials must be different"
        )

    backup_directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S-%fZ")
    destination = backup_directory / f"clearspend-{label}-{timestamp}.dump.enc"
    partial = destination.with_name(destination.name + ".partial")
    if destination.exists() or partial.exists():
        raise PostgreSQLBackupError("PostgreSQL backup destination already exists")

    database_environment = _database_environment(settings, database_password)
    encryption_environment = _encryption_environment(encryption_passphrase)
    try:
        pipeline_runner(
            _pg_dump_command(pg_dump_path, settings),
            database_environment,
            _encrypt_command(openssl_path, partial),
            encryption_environment,
        )
        if not partial.is_file() or partial.stat().st_size == 0:
            raise PostgreSQLBackupError("Encrypted PostgreSQL backup was not created")
        partial.chmod(0o600)

        listing_bytes = pipeline_runner(
            _decrypt_command(openssl_path, partial),
            encryption_environment,
            _pg_restore_list_command(pg_restore_path),
            database_environment,
        )
        try:
            listing = listing_bytes.decode("utf-8")
        except UnicodeDecodeError as error:
            raise PostgreSQLBackupError("PostgreSQL backup listing is invalid") from error
        missing_tables = EXPECTED_CLEARSPEND_TABLES - _listed_tables(listing)
        if missing_tables:
            raise PostgreSQLBackupError(
                "PostgreSQL backup is missing required ClearSpend tables"
            )
        partial.replace(destination)
        return destination
    except BaseException:
        partial.unlink(missing_ok=True)
        destination.unlink(missing_ok=True)
        raise


def restore_verified_postgresql_backup(
    archive: Path,
    target: PostgreSQLSettings,
    *,
    encryption_keychain_service: str,
    encryption_keychain_account: str,
    psql_path: Path = Path("psql"),
    pg_restore_path: Path = Path("pg_restore"),
    openssl_path: Path = Path("openssl"),
    password_loader: PasswordLoader = load_keychain_password,
    pipeline_runner: PipelineRunner = _run_pipeline,
    command_runner: CommandRunner = _run_command,
) -> None:
    """Restore an encrypted archive only into a target without the private schema."""
    if not archive.is_file() or archive.stat().st_size == 0:
        raise PostgreSQLBackupError("Encrypted PostgreSQL backup does not exist")
    if not target.ssl_root_certificate.is_file():
        raise PostgreSQLBackupError("PostgreSQL root certificate does not exist")

    database_password = password_loader(target.keychain_service, target.keychain_account)
    encryption_passphrase = password_loader(
        encryption_keychain_service, encryption_keychain_account
    )
    if database_password == encryption_passphrase:
        raise PostgreSQLBackupError(
            "PostgreSQL and backup-encryption credentials must be different"
        )
    database_environment = _database_environment(target, database_password)
    encryption_environment = _encryption_environment(encryption_passphrase)

    preflight = command_runner(
        _psql_command(
            psql_path,
            target,
            "SELECT CASE WHEN to_regnamespace('clearspend') IS NULL "
            "THEN 'empty' ELSE 'occupied' END",
        ),
        database_environment,
    ).decode("utf-8", errors="replace").strip()
    if preflight != "empty":
        raise PostgreSQLBackupError("PostgreSQL recovery target is not empty")

    pipeline_runner(
        _decrypt_command(openssl_path, archive),
        encryption_environment,
        _pg_restore_command(pg_restore_path, target),
        database_environment,
    )
    table_names = ",".join(
        "'" + table + "'" for table in sorted(EXPECTED_CLEARSPEND_TABLES)
    )
    verification = command_runner(
        _psql_command(
            psql_path,
            target,
            "SELECT COUNT(*)::TEXT || ':' || "
            "(SELECT COUNT(*)::TEXT FROM clearspend.schema_migrations) "
            "FROM information_schema.tables WHERE table_schema='clearspend' "
            f"AND table_name IN ({table_names})",
        ),
        database_environment,
    ).decode("utf-8", errors="replace").strip()
    if verification != f"{len(EXPECTED_CLEARSPEND_TABLES)}:4":
        raise PostgreSQLBackupError("PostgreSQL recovery contents are incomplete")
