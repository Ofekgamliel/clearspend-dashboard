"""Internal read models needed only by backend observation analysis."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable

from clearspend.database.connection import connect_database
from clearspend.reporting.sql import REPORTING_MONTH_SQL


def _plan_identity(row: dict) -> str:
    """Build a stable identity for one installment purchase plan."""
    return json.dumps(
        [
            row.get("provider") or "",
            row.get("card_last4") or "",
            row.get("canonical_merchant_id") or "",
            row.get("transaction_date") or "",
            row.get("original_amount") or "",
            row.get("original_currency") or "",
            int(row.get("installment_total") or 0),
        ],
        ensure_ascii=False,
        separators=(",", ":"),
    )


def historical_installments_payload(
    database: Path,
    months: Iterable[str],
    card: str,
) -> dict[str, dict]:
    """Return month-indexed installment totals and stable plan membership.

    This is intentionally not an HTTP response. It supplies plan identity that
    the public recurring payload does not need to expose.
    """
    selected_months = tuple(sorted(dict.fromkeys(
        str(month) for month in months if month
    )))
    if not selected_months:
        return {}
    placeholders = ",".join("?" for _month in selected_months)
    card_sql = ""
    parameters: list[object] = [*selected_months]
    if card != "all" and ":" in card:
        provider, last4 = card.split(":", 1)
        card_sql = " AND t.provider=? AND t.card_last4=?"
        parameters.extend([provider, last4])

    connection = connect_database(database)
    try:
        rows = [dict(row) for row in connection.execute(
            f"""SELECT t.provider,t.card_last4,
            COALESCE(d.canonical_group_id,t.merchant_normalized) canonical_merchant_id,
            COALESCE(d.display_name,t.merchant_raw) display_name,
            t.merchant_raw source_alias,t.transaction_date,t.original_amount,
            t.original_currency,t.installment_total,{REPORTING_MONTH_SQL} report_month,
            CAST(t.charged_amount AS REAL) amount
            FROM transactions t
            LEFT JOIN merchant_display_mappings d
              ON d.merchant_normalized=t.merchant_normalized
            WHERE t.installment_number IS NOT NULL
              AND CAST(t.charged_amount AS REAL)>0
              AND {REPORTING_MONTH_SQL} IN ({placeholders}){card_sql}
            ORDER BY report_month,t.id""",
            parameters,
        )]
    finally:
        connection.close()

    result = {
        month: {"installment_billed": 0.0, "plans": {}}
        for month in selected_months
    }
    for row in rows:
        month = str(row["report_month"])
        month_payload = result[month]
        month_payload["installment_billed"] += float(row["amount"] or 0)
        plan_id = _plan_identity(row)
        month_payload["plans"].setdefault(plan_id, {
            "plan_id": plan_id,
            "display_name": row.get("display_name") or "",
            "source_alias": row.get("source_alias") or "",
            "original_purchase_date": row.get("transaction_date") or "",
            "original_amount": row.get("original_amount") or "",
            "installment_total": int(row.get("installment_total") or 0),
        })
    return {
        month: {
            "installment_billed": round(payload["installment_billed"], 2),
            "plans": tuple(payload["plans"].values()),
        }
        for month, payload in result.items()
    }
