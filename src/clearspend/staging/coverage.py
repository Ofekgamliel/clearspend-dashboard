from __future__ import annotations

import sqlite3
from datetime import datetime

from clearspend.imports.domain import parse_statement_month


def staged_statement_coverage(connection: sqlite3.Connection, statement) -> tuple[list[dict], list[dict]]:
    """Describe statement coverage and compare it with prior imported periods."""
    groups: dict[str, list] = {}
    for item in statement.transactions:
        groups.setdefault(item.card_last4, []).append(item)
    statement_month = parse_statement_month(statement.date_range)
    coverage: list[dict] = []
    warnings: list[dict] = []
    has_coverage_table = bool(connection.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='import_coverage'"
    ).fetchone())
    for card_last4, rows in groups.items():
        purchase_dates = [item.transaction_date for item in rows if item.transaction_date]
        billing_dates = [item.billing_date for item in rows if item.billing_date]
        pending = [item for item in rows if item.charged_amount is None]
        outside_cycle = [item for item in rows if item.source_sheet.endswith(":immediate")]
        item = {
            "card_last4": card_last4,
            "statement_month": statement_month,
            "statement_period": statement.date_range,
            "statement_as_of_date": statement.statement_as_of_date,
            "purchase_date_from": min(purchase_dates) if purchase_dates else None,
            "purchase_date_to": max(purchase_dates) if purchase_dates else None,
            "billing_date_from": min(billing_dates) if billing_dates else None,
            "billing_date_to": max(billing_dates) if billing_dates else None,
            "finalized_rows": len(rows) - len(pending),
            "pending_rows": len(pending),
            "outside_cycle_rows": len(outside_cycle),
            "official_total": statement.official_total if len(groups) == 1 else None,
        }
        coverage.append(item)
        if not has_coverage_table:
            continue
        previous = connection.execute(
            """SELECT c.*,i.original_name,i.imported_at FROM import_coverage c
            JOIN imports i ON i.id=c.import_id
            WHERE c.card_last4=? AND i.status='imported'
            ORDER BY COALESCE(c.statement_month,'' ) DESC,i.id DESC""",
            (card_last4,),
        ).fetchall()
        overlapping = [row for row in previous if item["purchase_date_from"] and item["purchase_date_to"]
                       and row["purchase_date_from"] and row["purchase_date_to"]
                       and item["purchase_date_from"] <= row["purchase_date_to"]
                       and item["purchase_date_to"] >= row["purchase_date_from"]]
        if overlapping:
            warnings.append({
                "type": "overlap", "card_last4": card_last4,
                "message": f"Purchase dates overlap {len(overlapping)} earlier import(s)",
                "imports": [row["original_name"] for row in overlapping[:3]],
            })
        previous_months = [row["statement_month"] for row in previous if row["statement_month"]]
        if statement_month and previous_months:
            latest_month = max(previous_months)
            incoming = datetime.strptime(statement_month, "%Y-%m")
            latest = datetime.strptime(latest_month, "%Y-%m")
            distance = (incoming.year - latest.year) * 12 + incoming.month - latest.month
            if distance <= 0:
                warnings.append({
                    "type": "older_period", "card_last4": card_last4,
                    "message": f"Statement period is not newer than the latest imported period ({latest_month})",
                })
            elif distance > 1:
                warnings.append({
                    "type": "coverage_gap", "card_last4": card_last4,
                    "message": f"There are {distance - 1} unimported statement month(s) before this file",
                })
    return coverage, warnings


def save_import_coverage(
    connection: sqlite3.Connection,
    import_id: int,
    coverage_rows: list[dict],
) -> None:
    """Persist reviewed statement coverage for an imported statement."""
    for coverage in coverage_rows:
        connection.execute(
            """INSERT OR REPLACE INTO import_coverage(
            import_id,card_last4,statement_month,statement_period,
            statement_as_of_date,purchase_date_from,purchase_date_to,
            billing_date_from,billing_date_to,finalized_rows,pending_rows,
            outside_cycle_rows,official_total
            ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                import_id, coverage["card_last4"], coverage["statement_month"],
                coverage["statement_period"], coverage["statement_as_of_date"],
                coverage["purchase_date_from"], coverage["purchase_date_to"],
                coverage["billing_date_from"], coverage["billing_date_to"],
                coverage["finalized_rows"], coverage["pending_rows"],
                coverage["outside_cycle_rows"], coverage["official_total"],
            ),
        )
