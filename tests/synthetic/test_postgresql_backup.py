from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from typing import Mapping, Sequence

from clearspend.database.postgresql_backup import (
    EXPECTED_CLEARSPEND_TABLES,
    PostgreSQLBackupError,
    _write_integrity_manifest,
    create_verified_postgresql_backup,
    restore_verified_postgresql_backup,
    verify_postgresql_backup,
)
from clearspend.database.settings import PostgreSQLSettings


def archive_listing(tables: frozenset[str] = EXPECTED_CLEARSPEND_TABLES) -> bytes:
    return "\n".join(
        f"1; 1259 1 TABLE clearspend {table} postgres" for table in sorted(tables)
    ).encode("utf-8")


class SyntheticPipeline:
    def __init__(self, listing: bytes = archive_listing()) -> None:
        self.listing = listing
        self.calls: list[
            tuple[Sequence[str], Mapping[str, str], Sequence[str], Mapping[str, str]]
        ] = []

    def __call__(
        self,
        first_command: Sequence[str],
        first_environment: Mapping[str, str],
        second_command: Sequence[str],
        second_environment: Mapping[str, str],
    ) -> bytes:
        self.calls.append(
            (first_command, first_environment, second_command, second_environment)
        )
        if "--format=custom" in first_command:
            output_index = second_command.index("-out") + 1
            Path(second_command[output_index]).write_bytes(b"synthetic-encrypted-archive")
            return b""
        return self.listing


class PostgreSQLBackupTests(unittest.TestCase):
    def settings(self, certificate: Path) -> PostgreSQLSettings:
        return PostgreSQLSettings(
            host="db.synthetic.invalid",
            port=5432,
            database="postgres",
            user="postgres.synthetic",
            ssl_root_certificate=certificate,
            keychain_service="clearspend-synthetic-admin",
            keychain_account="postgres",
        )

    def test_backup_is_encrypted_verified_private_and_keeps_secrets_out_of_arguments(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            certificate = root / "ca.crt"
            certificate.touch()
            pipeline = SyntheticPipeline()
            loaded_credentials: list[tuple[str, str]] = []

            def load_password(service: str, account: str) -> str:
                loaded_credentials.append((service, account))
                if account == "postgres":
                    return "synthetic-database-secret"
                return "synthetic-encryption-secret"

            destination = create_verified_postgresql_backup(
                self.settings(certificate),
                root / "backups",
                "synthetic",
                encryption_keychain_service="clearspend-synthetic-backup",
                encryption_keychain_account="archive",
                password_loader=load_password,
                pipeline_runner=pipeline,
            )

            self.assertTrue(destination.is_file())
            self.assertTrue(destination.name.endswith(".dump.enc"))
            self.assertEqual(destination.stat().st_mode & 0o777, 0o600)
            integrity = destination.with_name(destination.name + ".integrity")
            self.assertTrue(integrity.is_file())
            self.assertEqual(integrity.stat().st_mode & 0o777, 0o600)
            self.assertEqual(len(pipeline.calls), 2)
            all_arguments = " ".join(
                argument
                for call in pipeline.calls
                for command in (call[0], call[2])
                for argument in command
            )
            self.assertNotIn("synthetic-database-secret", all_arguments)
            self.assertNotIn("synthetic-encryption-secret", all_arguments)
            self.assertEqual(
                pipeline.calls[0][1]["PGPASSWORD"],
                "synthetic-database-secret",
            )
            self.assertNotIn("PGPASSWORD", pipeline.calls[0][3])
            self.assertEqual(
                pipeline.calls[0][3]["CLEARSPEND_BACKUP_PASSPHRASE"],
                "synthetic-encryption-secret",
            )
            self.assertEqual(
                loaded_credentials,
                [
                    ("clearspend-synthetic-admin", "postgres"),
                    ("clearspend-synthetic-backup", "archive"),
                ],
            )

    def test_missing_required_table_rejects_and_removes_archive(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            certificate = root / "ca.crt"
            certificate.touch()
            pipeline = SyntheticPipeline(
                archive_listing(EXPECTED_CLEARSPEND_TABLES - {"transactions"})
            )

            with self.assertRaisesRegex(PostgreSQLBackupError, "missing required"):
                create_verified_postgresql_backup(
                    self.settings(certificate),
                    root / "backups",
                    "synthetic",
                    encryption_keychain_service="clearspend-synthetic-backup",
                    encryption_keychain_account="archive",
                    password_loader=lambda service, account: (
                        "database-secret" if account == "postgres" else "encryption-secret"
                    ),
                    pipeline_runner=pipeline,
                )

            self.assertEqual(list((root / "backups").iterdir()), [])

    def test_pipeline_failure_removes_partial_archive(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            certificate = root / "ca.crt"
            certificate.touch()

            def fail_after_partial_write(
                first_command: Sequence[str],
                first_environment: Mapping[str, str],
                second_command: Sequence[str],
                second_environment: Mapping[str, str],
            ) -> bytes:
                output_index = second_command.index("-out") + 1
                Path(second_command[output_index]).write_bytes(b"partial-private-data")
                raise PostgreSQLBackupError("synthetic pipeline failure")

            with self.assertRaisesRegex(PostgreSQLBackupError, "synthetic pipeline"):
                create_verified_postgresql_backup(
                    self.settings(certificate),
                    root / "backups",
                    "synthetic",
                    encryption_keychain_service="clearspend-synthetic-backup",
                    encryption_keychain_account="archive",
                    password_loader=lambda service, account: (
                        "database-secret" if account == "postgres" else "encryption-secret"
                    ),
                    pipeline_runner=fail_after_partial_write,
                )

            self.assertEqual(list((root / "backups").iterdir()), [])

    def test_rejects_reused_password_invalid_label_and_missing_certificate(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            certificate = root / "ca.crt"
            certificate.touch()
            settings = self.settings(certificate)

            with self.assertRaisesRegex(PostgreSQLBackupError, "must be different"):
                create_verified_postgresql_backup(
                    settings,
                    root / "backups",
                    "synthetic",
                    encryption_keychain_service="clearspend-synthetic-backup",
                    encryption_keychain_account="archive",
                    password_loader=lambda service, account: "reused-secret",
                    pipeline_runner=SyntheticPipeline(),
                )
            with self.assertRaisesRegex(PostgreSQLBackupError, "label is invalid"):
                create_verified_postgresql_backup(
                    settings,
                    root / "backups",
                    "../unsafe",
                    encryption_keychain_service="clearspend-synthetic-backup",
                    encryption_keychain_account="archive",
                    password_loader=lambda service, account: "unused",
                    pipeline_runner=SyntheticPipeline(),
                )
            with self.assertRaisesRegex(PostgreSQLBackupError, "certificate"):
                create_verified_postgresql_backup(
                    self.settings(root / "missing-ca.crt"),
                    root / "backups",
                    "synthetic",
                    encryption_keychain_service="clearspend-synthetic-backup",
                    encryption_keychain_account="archive",
                    password_loader=lambda service, account: "unused",
                    pipeline_runner=SyntheticPipeline(),
                )

    def test_restore_requires_empty_target_and_verifies_complete_result(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            certificate = root / "ca.crt"
            certificate.touch()
            archive = root / "synthetic.dump.enc"
            archive.write_bytes(b"synthetic-encrypted-archive")
            _write_integrity_manifest(
                archive,
                archive.with_name(archive.name + ".integrity"),
                "encryption-secret",
            )
            commands: list[Sequence[str]] = []
            answers = iter((b"empty\n", b"16:5\n"))

            def run_command(
                command: Sequence[str], environment: Mapping[str, str]
            ) -> bytes:
                commands.append(command)
                self.assertEqual(environment["PGPASSWORD"], "database-secret")
                return next(answers)

            pipeline = SyntheticPipeline()
            restore_verified_postgresql_backup(
                archive,
                self.settings(certificate),
                encryption_keychain_service="clearspend-synthetic-backup",
                encryption_keychain_account="archive",
                password_loader=lambda service, account: (
                    "database-secret" if account == "postgres" else "encryption-secret"
                ),
                pipeline_runner=pipeline,
                command_runner=run_command,
            )

            self.assertEqual(len(commands), 2)
            self.assertEqual(len(pipeline.calls), 1)
            arguments = " ".join((*pipeline.calls[0][0], *pipeline.calls[0][2]))
            self.assertNotIn("database-secret", arguments)
            self.assertNotIn("encryption-secret", arguments)
            self.assertIn("--single-transaction", pipeline.calls[0][2])

    def test_standalone_verification_authenticates_and_lists_archive(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            archive = root / "synthetic.dump.enc"
            archive.write_bytes(b"synthetic-encrypted-archive")
            _write_integrity_manifest(
                archive,
                archive.with_name(archive.name + ".integrity"),
                "encryption-secret",
            )
            pipeline = SyntheticPipeline()

            verify_postgresql_backup(
                archive,
                encryption_keychain_service="clearspend-synthetic-backup",
                encryption_keychain_account="archive",
                password_loader=lambda service, account: "encryption-secret",
                pipeline_runner=pipeline,
            )

            self.assertEqual(len(pipeline.calls), 1)
            self.assertNotIn("PGPASSWORD", pipeline.calls[0][3])
            self.assertNotIn(
                "CLEARSPEND_BACKUP_PASSPHRASE",
                pipeline.calls[0][3],
            )
            self.assertIn("PATH", pipeline.calls[0][3])
            self.assertIn("--list", pipeline.calls[0][2])

    def test_restore_refuses_occupied_target_before_decryption(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            certificate = root / "ca.crt"
            certificate.touch()
            archive = root / "synthetic.dump.enc"
            archive.write_bytes(b"synthetic-encrypted-archive")
            _write_integrity_manifest(
                archive,
                archive.with_name(archive.name + ".integrity"),
                "encryption-secret",
            )
            pipeline = SyntheticPipeline()

            with self.assertRaisesRegex(PostgreSQLBackupError, "not empty"):
                restore_verified_postgresql_backup(
                    archive,
                    self.settings(certificate),
                    encryption_keychain_service="clearspend-synthetic-backup",
                    encryption_keychain_account="archive",
                    password_loader=lambda service, account: (
                        "database-secret"
                        if account == "postgres"
                        else "encryption-secret"
                    ),
                    pipeline_runner=pipeline,
                    command_runner=lambda command, environment: b"occupied\n",
                )

            self.assertEqual(pipeline.calls, [])

    def test_restore_rejects_tampered_archive_before_target_access(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            certificate = root / "ca.crt"
            certificate.touch()
            archive = root / "synthetic.dump.enc"
            archive.write_bytes(b"synthetic-encrypted-archive")
            _write_integrity_manifest(
                archive,
                archive.with_name(archive.name + ".integrity"),
                "encryption-secret",
            )
            archive.write_bytes(b"tampered-encrypted-archive")

            with self.assertRaisesRegex(PostgreSQLBackupError, "integrity"):
                restore_verified_postgresql_backup(
                    archive,
                    self.settings(certificate),
                    encryption_keychain_service="clearspend-synthetic-backup",
                    encryption_keychain_account="archive",
                    password_loader=lambda service, account: (
                        "database-secret"
                        if account == "postgres"
                        else "encryption-secret"
                    ),
                    pipeline_runner=SyntheticPipeline(),
                    command_runner=lambda command, environment: self.fail(
                        "target must not be accessed before integrity verification"
                    ),
                )

    def test_restore_rejects_archive_without_integrity_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            certificate = root / "ca.crt"
            certificate.touch()
            archive = root / "legacy.dump.enc"
            archive.write_bytes(b"legacy-encrypted-archive")

            with self.assertRaisesRegex(PostgreSQLBackupError, "integrity"):
                restore_verified_postgresql_backup(
                    archive,
                    self.settings(certificate),
                    encryption_keychain_service="clearspend-synthetic-backup",
                    encryption_keychain_account="archive",
                    password_loader=lambda service, account: (
                        "database-secret"
                        if account == "postgres"
                        else "encryption-secret"
                    ),
                    pipeline_runner=SyntheticPipeline(),
                    command_runner=lambda command, environment: self.fail(
                        "legacy archive must fail before target access"
                    ),
                )


if __name__ == "__main__":
    unittest.main()
