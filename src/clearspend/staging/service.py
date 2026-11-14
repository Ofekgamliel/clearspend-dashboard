from __future__ import annotations

import shutil
from datetime import datetime
from pathlib import Path

from clearspend.import_engine import ImportDatabase
from clearspend.staging.coverage import save_import_coverage
from clearspend.staging.decisions import (
    apply_imported_transaction_decisions,
    apply_permanent_merchant_decisions,
    merchant_decision_map,
    merchants_requiring_review,
    reviewed_duplicate_matches,
)


def commit_staged_batch(
    database: Path,
    batch: dict,
    decisions: list[dict],
    duplicate_decisions: list[dict],
    analysis: dict,
) -> dict:
    """Commit a reviewed staged batch after creating a recoverable database backup."""
    decision_map = merchant_decision_map(decisions)
    review_required_merchants = merchants_requiring_review(analysis)
    backup_dir = database.parent / "backups"
    backup_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
    backup_path = backup_dir / f"clearspend-before-import-{stamp}.db"
    shutil.copy2(database, backup_path)
    db = ImportDatabase(database)
    results: list[dict] = []
    try:
        reviewed_matches_by_file = reviewed_duplicate_matches(analysis, duplicate_decisions)
        now = datetime.now().astimezone().isoformat()
        apply_permanent_merchant_decisions(db.connection, decision_map, now)
        db.connection.commit()
        for file_index, staged_file in enumerate(batch["uploads"]):
            pending_keys = {
                item["transaction_key"] for item in analysis.get("pending_transactions", [])
                if int(item["file_index"]) == file_index
            }
            result = db.import_file(
                staged_file["path"],
                probable_duplicate_matches=reviewed_matches_by_file.get(file_index),
                excluded_transaction_keys=pending_keys,
            )
            if result.get("import_id"):
                table = "income_imports" if result.get("kind") == "income" else "imports"
                db.connection.execute(
                    f"UPDATE {table} SET original_name=? WHERE id=?",
                    (staged_file["filename"], result["import_id"]),
                )
                if result.get("kind") != "income":
                    save_import_coverage(
                        db.connection,
                        result["import_id"],
                        analysis["files"][file_index].get("coverage", []),
                    )
            excluded = 0
            if result.get("import_id") and result.get("kind") != "income":
                excluded = apply_imported_transaction_decisions(
                    db.connection,
                    result["import_id"],
                    decision_map,
                    review_required_merchants,
                    now,
                )
                if excluded:
                    db.connection.execute(
                        "UPDATE imports SET inserted_rows=MAX(inserted_rows-?,0) WHERE id=?",
                        (excluded, result["import_id"]),
                    )
                    result["inserted"] = max(int(result.get("inserted", 0)) - excluded, 0)
                    result["excluded"] = excluded
            db.connection.commit()
            result["filename"] = staged_file["filename"]
            results.append(result)
        return {"status": "committed", "backup": str(backup_path), "results": results}
    finally:
        db.close()
