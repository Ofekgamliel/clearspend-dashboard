"""Read-model assembly for category totals and month-over-month comparisons."""

from __future__ import annotations

from pathlib import Path

from clearspend.database.connection import connect_database
from clearspend.reporting.categories import (
    with_previous_month_comparison,
    with_spending_shares,
)
from clearspend.reporting.periods import shift_month
from clearspend.reporting.personal_spending import personal_spending_sql
from clearspend.reporting.queries import filtered_where


def categories_payload(
    database: Path,
    period: str,
    card: str,
    month: str = "",
    event_scope: str = "all",
) -> dict:
    connection = connect_database(database)
    try:
        where, parameters, period_data = filtered_where(
            connection, period, card, month, event_scope
        )
        total = float(connection.execute(
            f"SELECT COALESCE(SUM({personal_spending_sql()}),0) "
            f"FROM transactions t WHERE {where}",
            parameters,
        ).fetchone()[0])
        rows = with_spending_shares(connection.execute(
            f"""SELECT COALESCE(o.category,t.user_category,t.provider_category,'Needs review') category,
            ROUND(SUM({personal_spending_sql()}),2) amount,
            COUNT(*) transactions,
            COUNT(DISTINCT COALESCE(d.canonical_group_id,t.merchant_normalized)) merchants
            FROM transactions t LEFT JOIN merchant_display_mappings d
              ON d.merchant_normalized=t.merchant_normalized
            LEFT JOIN transaction_category_overrides o ON o.transaction_id=t.id
            WHERE {where}
            GROUP BY COALESCE(o.category,t.user_category,t.provider_category,'Needs review')
            ORDER BY amount DESC""",
            parameters,
        ), total)
        category_comparison = {"available": False, "previous_month": None}
        if period == "month":
            previous_month = shift_month((period_data["start"] or month)[:7], -1)
            previous_where, previous_parameters, _ = filtered_where(
                connection, "month", card, previous_month, event_scope
            )
            previous_count = int(connection.execute(
                f"SELECT COUNT(*) FROM transactions t WHERE {previous_where}",
                previous_parameters,
            ).fetchone()[0])
            previous_rows = connection.execute(
                f"""SELECT COALESCE(o.category,t.user_category,t.provider_category,'Needs review') category,
                ROUND(SUM({personal_spending_sql()}),2) amount
                FROM transactions t
                LEFT JOIN transaction_category_overrides o ON o.transaction_id=t.id
                WHERE {previous_where}
                GROUP BY COALESCE(o.category,t.user_category,t.provider_category,'Needs review')""",
                previous_parameters,
            ).fetchall()
            previous_amounts = {
                row["category"]: float(row["amount"]) for row in previous_rows
            }
            category_comparison = {
                "available": previous_count > 0,
                "previous_month": previous_month,
            }
            rows = with_previous_month_comparison(
                rows,
                previous_transaction_count=previous_count,
                previous_amounts=previous_amounts,
            )
        return {
            "period": period_data,
            "selected_card": card,
            "event_scope": event_scope,
            "total": round(total, 2),
            "categories": rows,
            "category_comparison": category_comparison,
        }
    finally:
        connection.close()
