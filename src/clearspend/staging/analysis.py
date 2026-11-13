from __future__ import annotations

from pathlib import Path

from clearspend.database.connection import connect_database
from clearspend.import_engine import is_income_xlsx, parse_income_xlsx, parse_statement
from clearspend.staging.coverage import staged_statement_coverage
from clearspend.staging.duplicates import possible_duplicate_matches
from clearspend.staging.file_analysis import (
    analyze_staged_income_file,
    analyze_staged_statement_file,
)
from clearspend.staging.merchants import (
    add_staged_merchant_transactions,
    resolve_staged_merchants,
)
from clearspend.staging.references import staged_reference_data
from clearspend.staging.rules import staged_transaction_summary, statement_reconciliation_total
from tools.profile_samples import sha256_path


def analyze_staged_files(database: Path, uploads: list[tuple[str, Path]]) -> dict:
    """Analyze uploads against existing data without writing to the database."""
    connection = connect_database(database)
    try:
        categories, identities = staged_reference_data(connection)
        files: list[dict] = []
        merchant_groups: dict[str, dict] = {}
        exact_duplicates: list[dict] = []
        possible_duplicates: list[dict] = []
        new_transactions: list[dict] = []
        pending_transactions: list[dict] = []
        coverage_warnings: list[dict] = []
        seen_batch_keys: dict[str, dict] = {}
        for file_index, (original_name, path) in enumerate(uploads):
            byte_hash = sha256_path(path)
            if path.suffix.lower() == ".xlsx" and is_income_xlsx(path):
                entries = parse_income_xlsx(path)
                result = analyze_staged_income_file(
                    connection,
                    original_name=original_name,
                    path=path,
                    file_index=file_index,
                    byte_hash=byte_hash,
                    entries=entries,
                )
                files.append(result["file"])
                exact_duplicates.extend(result["exact_duplicates"])
                continue

            statement = parse_statement(path)
            result = analyze_staged_statement_file(
                connection,
                original_name=original_name,
                path=path,
                file_index=file_index,
                byte_hash=byte_hash,
                statement=statement,
                seen_batch_keys=seen_batch_keys,
            )
            files.append(result["file"])
            exact_duplicates.extend(result["exact_duplicates"])
            possible_duplicates.extend(result["possible_duplicates"])
            new_transactions.extend(result["new_transactions"])
            pending_transactions.extend(result["pending_transactions"])
            coverage_warnings.extend(result["coverage_warnings"])
            if result["file"]["status"] in {"duplicate_file", "duplicate_content"}:
                continue
            add_staged_merchant_transactions(
                merchant_groups,
                statement.transactions,
                duplicate_keys=result["duplicate_keys"],
                pending_keys=result["pending_keys"],
            )
        merchants = resolve_staged_merchants(connection, merchant_groups)
        return {
            "files": files,
            "merchants": merchants,
            "categories": categories,
            "display_identities": identities,
            "exact_duplicates": exact_duplicates,
            "possible_duplicates": possible_duplicates,
            "new_transactions": new_transactions,
            "pending_transactions": pending_transactions,
            "coverage_warnings": coverage_warnings,
        }
    finally:
        connection.close()
