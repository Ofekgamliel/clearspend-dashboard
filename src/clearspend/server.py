from __future__ import annotations

import argparse
from http.server import ThreadingHTTPServer
from pathlib import Path

from clearspend.import_engine import (
    ImportDatabase,
)
from clearspend.http.multipart import parse_multipart_files
from clearspend.http.json_body import read_json_object
from clearspend.http.imports import commit_staged_import, process_import_uploads
from clearspend.http.handler import ClearSpendHandler
from clearspend.http.api import (
    JSON_GET_PATHS,
    JSON_POST_PATHS,
    dispatch_json_get,
    dispatch_json_post,
)
from clearspend.merchants.service import save_mapping, save_merchant
from clearspend.merchants.queries import mapping_payload, merchants_payload
from clearspend.database.migration_runner import migrate_database
from clearspend.events.queries import events_payload
from clearspend.events.service import create_event, save_event_settings, save_transaction_event
from clearspend.observations.queries import observation_reviews_payload
from clearspend.observations.service import save_observation_review
from clearspend.recurring.queries import recurring_payload
from clearspend.recurring.service import manage_recurring_profile, save_recurring_profile
from clearspend.reporting.category_queries import categories_payload
from clearspend.reporting.dashboard import dashboard_payload
from clearspend.staging.analysis import (
    analyze_staged_files,
    staged_reference_data,
    statement_reconciliation_total,
)
from clearspend.staging.service import commit_staged_batch
from clearspend.transactions.service import (
    save_transaction_adjustment,
    save_transaction_category,
)
from clearspend.transactions.queries import transactions_payload


class ClearSpendServer(ThreadingHTTPServer):
    def __init__(self, address: tuple[str, int], static_dir: Path, database: Path):
        super().__init__(address, ClearSpendHandler)
        self.static_dir = static_dir
        self.database = database
        self.staged_imports: dict[str, dict] = {}


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the local ClearSpend dashboard")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--database", type=Path)
    parser.add_argument("--static-dir", type=Path)
    parser.add_argument(
        "--migrate-database",
        action="store_true",
        help="back up and migrate the database, then exit without starting the server",
    )
    args = parser.parse_args()
    project_root = Path(__file__).resolve().parents[2]
    database = (args.database or project_root / "data" / "clearspend.db").resolve()
    static_dir = (args.static_dir or project_root / "dist").resolve()
    if args.migrate_database:
        result = migrate_database(database, database.parent / "backups")
        print(f"Database schema version: {result.ending_version}")
        if result.applied_versions:
            print("Applied migrations: " + ", ".join(map(str, result.applied_versions)))
        else:
            print("No migrations were pending")
        if result.backup_path:
            print(f"Backup: {result.backup_path}")
        return
    migration = ImportDatabase(database)
    migration.close()
    server = ClearSpendServer((args.host, args.port), static_dir, database)
    print(f"ClearSpend is running at http://{args.host}:{args.port}")
    print(f"Database: {database}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping ClearSpend")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
