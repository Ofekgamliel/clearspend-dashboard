from __future__ import annotations

import argparse
from http.server import ThreadingHTTPServer
from pathlib import Path

from clearspend.database.connection import DatabaseTarget
from clearspend.database.migration_runner import migrate_database
from clearspend.database.postgresql import PostgreSQLPool
from clearspend.database.postgresql_backup import PostgreSQLBackupConfiguration
from clearspend.database.postgresql_migration_runner import inspect_postgresql_schema
from clearspend.database.postgresql_migrations import CURRENT_POSTGRESQL_SCHEMA_VERSION
from clearspend.database.runtime_config import load_postgresql_runtime_configuration
from clearspend.http.handler import ClearSpendHandler
from clearspend.import_engine import ImportDatabase


class ClearSpendServer(ThreadingHTTPServer):
    def __init__(
        self,
        address: tuple[str, int],
        static_dir: Path,
        database: DatabaseTarget,
        local_state_directory: Path,
        postgresql_backup: PostgreSQLBackupConfiguration | None = None,
    ):
        super().__init__(address, ClearSpendHandler)
        self.static_dir = static_dir
        self.database = database
        self.local_state_directory = local_state_directory
        self.postgresql_backup = postgresql_backup
        self.staged_imports: dict[str, dict] = {}


def _prepare_private_directory(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True, mode=0o700)
    path.chmod(0o700)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the local ClearSpend dashboard")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument(
        "--legacy-sqlite-database",
        type=Path,
        help="explicit archival SQLite database for compatibility or inspection",
    )
    parser.add_argument("--postgresql-config", type=Path)
    parser.add_argument("--static-dir", type=Path)
    parser.add_argument(
        "--migrate-database",
        action="store_true",
        help="back up and migrate the SQLite database, then exit",
    )
    args = parser.parse_args()
    if (
        args.legacy_sqlite_database is not None
        and args.postgresql_config is not None
    ):
        parser.error(
            "Choose either --legacy-sqlite-database or --postgresql-config"
        )
    if args.migrate_database and args.postgresql_config is not None:
        parser.error("PostgreSQL migrations are an explicit administrative operation")
    if args.migrate_database and args.legacy_sqlite_database is None:
        parser.error("--migrate-database requires --legacy-sqlite-database")
    if (
        args.legacy_sqlite_database is None
        and args.postgresql_config is None
    ):
        parser.error(
            "Choose --postgresql-config for normal use or "
            "--legacy-sqlite-database for archival SQLite access"
        )

    project_root = Path(__file__).resolve().parents[2]
    static_dir = (args.static_dir or project_root / "dist").resolve()
    if args.postgresql_config is None:
        sqlite_path = args.legacy_sqlite_database.resolve()
        if args.migrate_database:
            result = migrate_database(sqlite_path, sqlite_path.parent / "backups")
            print(f"Database schema version: {result.ending_version}")
            if result.applied_versions:
                print("Applied migrations: " + ", ".join(map(str, result.applied_versions)))
            else:
                print("No migrations were pending")
            if result.backup_path:
                print(f"Backup: {result.backup_path}")
            return
        migration = ImportDatabase(sqlite_path)
        migration.close()
        database: DatabaseTarget = sqlite_path
        local_state_directory = sqlite_path.parent
        postgresql_backup = None
        pool = None
        database_label = "SQLite"
    else:
        configuration = load_postgresql_runtime_configuration(
            args.postgresql_config.resolve()
        )
        if not configuration.database.ssl_root_certificate.is_file():
            raise RuntimeError("PostgreSQL root certificate does not exist")
        _prepare_private_directory(configuration.local_state_directory)
        _prepare_private_directory(configuration.backup.directory)
        pool = PostgreSQLPool(configuration.database)
        pool.open()
        try:
            status = inspect_postgresql_schema(pool)
            if (
                status.state != "versioned"
                or status.version != CURRENT_POSTGRESQL_SCHEMA_VERSION
            ):
                raise RuntimeError("PostgreSQL schema is not current")
        except BaseException:
            pool.close()
            raise
        database = pool
        local_state_directory = configuration.local_state_directory
        postgresql_backup = configuration.backup
        database_label = "PostgreSQL"

    server = ClearSpendServer(
        (args.host, args.port),
        static_dir,
        database,
        local_state_directory,
        postgresql_backup,
    )
    print(f"ClearSpend is running at http://{args.host}:{args.port}")
    print(f"Database backend: {database_label}")
    if args.postgresql_config:
        print(f"Database region: {configuration.expected_region}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping ClearSpend")
    finally:
        server.server_close()
        if pool is not None:
            pool.close()


if __name__ == "__main__":
    main()
