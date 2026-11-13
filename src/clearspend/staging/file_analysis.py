from __future__ import annotations

import hashlib
import sqlite3
from pathlib import Path

from clearspend.staging.coverage import staged_statement_coverage
from clearspend.staging.duplicates import possible_duplicate_matches
from clearspend.staging.rules import staged_transaction_summary, statement_reconciliation_total


def analyze_staged_income_file(
    connection: sqlite3.Connection,
    *,
    original_name: str,
    path: Path,
    file_index: int,
    byte_hash: str,
    entries: list,
) -> dict:
    """Classify one parsed income workbook against existing imported data."""
    prior_file = connection.execute(
        """SELECT id FROM income_imports WHERE byte_hash=?
        AND status IN ('imported','duplicate_file') ORDER BY id LIMIT 1""",
        (byte_hash,),
    ).fetchone()
    exact_duplicates: list[dict] = []
    existing = 0
    for entry in entries:
        matched = connection.execute(
            "SELECT id FROM income_entries WHERE entry_key=?", (entry.entry_key,)
        ).fetchone()
        if matched:
            existing += 1
            exact_duplicates.append({
                "filename": original_name,
                "file_index": file_index,
                "kind": "income",
                "merchant": entry.source_name,
                "transaction_date": entry.month,
                "amount": entry.amount,
                "currency": "ILS",
                "card_last4": None,
                "matched_transaction_id": matched["id"],
                "reason": "Exact income entry already exists",
            })
    return {
        "file": {
            "filename": original_name,
            "kind": "income",
            "format": "Income XLSX",
            "provider": "income",
            "card_last4": None,
            "statement_range": None,
            "parsed": len(entries),
            "duplicates": existing,
            "exact_duplicates": existing,
            "possible_duplicates": 0,
            "new_rows": len(entries) - existing,
            "status": "duplicate_file" if prior_file else "ready",
            "reconciliation": {
                "official_total": None,
                "parsed_total": round(sum(float(entry.amount) for entry in entries), 2),
                "status": "not_applicable",
            },
        },
        "exact_duplicates": exact_duplicates,
    }


def analyze_staged_statement_file(
    connection: sqlite3.Connection,
    *,
    original_name: str,
    path: Path,
    file_index: int,
    byte_hash: str,
    statement,
    seen_batch_keys: dict[str, dict],
) -> dict:
    """Classify one parsed statement without changing persistent data."""
    prior_file = connection.execute(
        """SELECT id FROM imports WHERE byte_hash=?
        AND status IN ('imported','duplicate_file') ORDER BY id LIMIT 1""",
        (byte_hash,),
    ).fetchone()
    file_coverage, coverage_warnings = staged_statement_coverage(connection, statement)
    prior_semantic = connection.execute(
        """SELECT id FROM imports WHERE semantic_hash=?
        AND status IN ('imported','duplicate_content') ORDER BY id LIMIT 1""",
        (statement.semantic_hash,),
    ).fetchone()
    duplicate_keys: set[str] = set()
    possible_keys: set[str] = set()
    pending_keys: set[str] = set()
    exact_duplicates: list[dict] = []
    possible_duplicates: list[dict] = []
    new_transactions: list[dict] = []
    pending_transactions: list[dict] = []
    for item in statement.transactions:
        summary = staged_transaction_summary(item, original_name, file_index)
        if summary["source_status"] == "pending":
            pending_keys.add(item.transaction_key)
            pending_transactions.append({
                **summary,
                "kind": "statement",
                "reason": "Provider has not finalized this charge",
            })
            continue
        voucher_exact = None
        if item.voucher_number:
            voucher_exact = connection.execute(
                """SELECT id,voucher_number FROM transactions
                WHERE provider=? AND card_last4=? AND voucher_number=? AND base_key=?
                ORDER BY id LIMIT 1""",
                (item.provider, item.card_last4, item.voucher_number, item.base_key),
            ).fetchone()
        existing_row = connection.execute(
            "SELECT id,voucher_number FROM transactions WHERE transaction_key=?",
            (item.transaction_key,),
        ).fetchone()
        earlier = seen_batch_keys.get(item.transaction_key)
        key_collision_is_separate = bool(
            existing_row and item.voucher_number and existing_row["voucher_number"]
            and item.voucher_number != existing_row["voucher_number"]
        )
        batch_collision_is_separate = bool(
            earlier and item.voucher_number and earlier.get("voucher_number")
            and item.voucher_number != earlier["voucher_number"]
        )
        exact_row = voucher_exact or (None if key_collision_is_separate else existing_row)
        exact_batch = None if batch_collision_is_separate else earlier
        if exact_row or exact_batch:
            duplicate_keys.add(item.transaction_key)
            exact_duplicates.append({
                **summary,
                "kind": "statement",
                "matched_transaction_id": exact_row["id"] if exact_row else None,
                "reason": "Exact transaction identity already exists" if exact_row
                else f"Exact transaction also appears in {exact_batch['filename']}",
            })
        else:
            matches, reason = possible_duplicate_matches(connection, item)
            if matches:
                possible_keys.add(item.transaction_key)
                match_ids = [row["id"] for row in matches]
                candidate_seed = f"{file_index}:{item.transaction_key}:{','.join(map(str, match_ids))}"
                possible_duplicates.append({
                    **summary,
                    "candidate_id": hashlib.sha256(candidate_seed.encode()).hexdigest()[:24],
                    "kind": "statement",
                    "reason": reason,
                    "matched_transaction_ids": match_ids,
                    "matched_rows": [dict(row) for row in matches],
                })
            else:
                new_transactions.append({**summary, "kind": "statement"})
        seen_batch_keys.setdefault(item.transaction_key, summary)
    installment_plans = {
        (
            item.provider, item.card_last4, item.merchant_normalized,
            item.transaction_date, item.original_amount, item.installment_total,
        )
        for item in statement.transactions if item.installment_number is not None
    }
    parsed_total = statement_reconciliation_total(statement)
    official_total = float(statement.official_total) if statement.official_total is not None else None
    difference = round(parsed_total - official_total, 2) if official_total is not None else None
    reconciliation_status = (
        "matched" if difference is not None and abs(difference) <= .01
        else "mismatch" if difference is not None else "manual_required"
    )
    status = (
        "duplicate_file" if prior_file
        else "duplicate_content" if prior_semantic else "ready"
    )
    return {
        "file": {
            "filename": original_name,
            "kind": "statement",
            "format": path.suffix.upper().lstrip("."),
            "provider": statement.provider,
            "card_last4": statement.card_last4,
            "product_name": statement.product_name,
            "statement_range": statement.date_range,
            "parsed": len(statement.transactions),
            "duplicates": len(duplicate_keys),
            "exact_duplicates": len(duplicate_keys),
            "possible_duplicates": len(possible_keys),
            "new_rows": (
                len(statement.transactions) - len(duplicate_keys)
                - len(possible_keys) - len(pending_keys)
            ),
            "status": status,
            "pending_rows": len(pending_keys),
            "installment_plans": len(installment_plans),
            "coverage": file_coverage,
            "reconciliation": {
                "official_total": official_total,
                "parsed_total": parsed_total,
                "difference": difference,
                "status": reconciliation_status,
            },
        },
        "duplicate_keys": duplicate_keys,
        "pending_keys": pending_keys,
        "exact_duplicates": exact_duplicates,
        "possible_duplicates": possible_duplicates,
        "new_transactions": new_transactions,
        "pending_transactions": pending_transactions,
        "coverage_warnings": [
            {**warning, "filename": original_name} for warning in coverage_warnings
        ],
    }
