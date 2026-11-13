from __future__ import annotations

from datetime import date, datetime
from pathlib import Path

from clearspend.database.connection import connect_database
from clearspend.reporting.calculations import calculate_income_balance, calculate_monthly_averages
from clearspend.reporting.categories import with_previous_month_comparison, with_spending_shares
from clearspend.reporting.periods import shift_month
from clearspend.reporting.personal_spending import personal_spending_sql
from clearspend.reporting.purchase_activity import PurchaseActivityRow, build_purchase_activity
from clearspend.reporting.queries import period_bounds
from clearspend.reporting.scope import build_reporting_filter
from clearspend.reporting.sql import REPORTING_DATE_SQL, REPORTING_MONTH_SQL


def dashboard_payload(database: Path, period: str, card: str, month: str = "") -> dict:
    connection = connect_database(database)
    try:
        start, end, label = period_bounds(connection, period, month)
        period_parameters: list[object] = [(start or "0000-00")[:7], (end or "9999-99")[:7]]
        reporting_filter = build_reporting_filter(
            REPORTING_MONTH_SQL, start=start, end=end, card=card
        )
        parameters = list(reporting_filter.parameters)
        where = reporting_filter.where

        metrics = connection.execute(
            f"""SELECT
            COALESCE(SUM({personal_spending_sql()}),0) spent,
            COALESCE(ABS(SUM(CASE WHEN CAST(t.charged_amount AS REAL) < 0 THEN CAST(t.charged_amount AS REAL) ELSE 0 END)),0) refunds,
            COUNT(*) transactions,
            COUNT(DISTINCT {REPORTING_DATE_SQL}) active_days
            FROM transactions t WHERE {where}""",
            parameters,
        ).fetchone()
        spent = float(metrics["spent"])
        active_days = int(metrics["active_days"])

        income_row = connection.execute(
            """SELECT COALESCE(SUM(CAST(amount AS REAL)),0) total,COUNT(*) entries
            FROM income_entries WHERE month BETWEEN ? AND ?""",
            ((start or "0000-00-00")[:7], (end or "9999-99-99")[:7]),
        ).fetchone()
        all_card_spending = connection.execute(
            f"""SELECT
            COALESCE(SUM({personal_spending_sql()}),0) personal_spent,
            COALESCE(SUM(CASE WHEN CAST(t.charged_amount AS REAL)>0 THEN CAST(t.charged_amount AS REAL) ELSE 0 END),0) charges,
            COALESCE(ABS(SUM(CASE WHEN CAST(t.charged_amount AS REAL)<0 THEN CAST(t.charged_amount AS REAL) ELSE 0 END)),0) refunds
            FROM transactions t WHERE {REPORTING_MONTH_SQL} BETWEEN ? AND ?""",
            period_parameters,
        ).fetchone()
        balance = calculate_income_balance(
            income=float(income_row["total"]),
            personal_positive_spending=float(all_card_spending["personal_spent"]),
            gross_charges=float(all_card_spending["charges"]),
            refunds=float(all_card_spending["refunds"]),
        )

        if period == "month":
            average_start = connection.execute(
                """SELECT MIN(value) FROM (
                SELECT COALESCE(billing_month,substr(billing_date,1,7),substr(transaction_date,1,7))||'-01' value
                FROM transactions WHERE transaction_date IS NOT NULL OR billing_month IS NOT NULL
                UNION ALL SELECT month||'-01' value FROM income_entries
                )"""
            ).fetchone()[0] or start
        else:
            average_start = start
        average_end = min(datetime.strptime(end, "%Y-%m-%d").date(), date.today()).isoformat() if end else date.today().isoformat()
        average_parameters = [(average_start or "0000-00")[:7], average_end[:7]]
        monthly_spending_rows = connection.execute(
            f"""SELECT {REPORTING_MONTH_SQL} month,
            SUM({personal_spending_sql()})
            - ABS(SUM(CASE WHEN CAST(t.charged_amount AS REAL)<0 THEN CAST(t.charged_amount AS REAL) ELSE 0 END)) net
            FROM transactions t WHERE {REPORTING_MONTH_SQL} BETWEEN ? AND ? GROUP BY {REPORTING_MONTH_SQL}""",
            average_parameters,
        ).fetchall()
        monthly_spending = {row["month"]: float(row["net"]) for row in monthly_spending_rows}
        monthly_income_rows = connection.execute(
            """SELECT month,SUM(CAST(amount AS REAL)) total FROM income_entries
            WHERE month BETWEEN ? AND ? GROUP BY month""",
            (average_parameters[0][:7], average_parameters[1][:7]),
        ).fetchall()
        monthly_income = {row["month"]: float(row["total"]) for row in monthly_income_rows}
        averages = calculate_monthly_averages(
            monthly_spending,
            monthly_income,
            current_month=date.today().strftime("%Y-%m"),
        )

        cards = [dict(row) for row in connection.execute(
            f"""SELECT t.provider,t.card_last4,
            COALESCE((SELECT i.product_name FROM imports i WHERE i.provider=t.provider AND i.card_last4=t.card_last4
                      AND i.product_name IS NOT NULL ORDER BY i.id LIMIT 1), UPPER(t.provider)) product_name,
            ROUND(SUM({personal_spending_sql()}),2) amount,
            COUNT(*) transactions
            FROM transactions t WHERE COALESCE(t.billing_month,substr(t.billing_date,1,7),substr(t.transaction_date,1,7)) BETWEEN ? AND ?
            GROUP BY t.provider,t.card_last4 ORDER BY amount DESC""",
            period_parameters,
        )]
        cards_total = sum(float(item["amount"]) for item in cards)
        for item in cards:
            item["key"] = f"{item['provider']}:{item['card_last4']}"
            item["share"] = round((item["amount"] / cards_total * 100), 1) if cards_total else 0

        categories = with_spending_shares(connection.execute(
            f"""SELECT COALESCE(o.category,t.user_category,t.provider_category,'Needs review') category,
            ROUND(SUM({personal_spending_sql()}),2) amount,
            COUNT(*) transactions FROM transactions t
            LEFT JOIN transaction_category_overrides o ON o.transaction_id=t.id WHERE {where}
            GROUP BY COALESCE(o.category,t.user_category,t.provider_category,'Needs review') HAVING amount > 0 ORDER BY amount DESC""",
            parameters,
        ), spent)

        category_comparison = {"available": False, "previous_month": None}
        if period == "month":
            previous_month = shift_month(start[:7], -1)
            previous_conditions = [f"{REPORTING_MONTH_SQL} = ?"]
            previous_parameters: list[object] = [previous_month]
            if card != "all" and ":" in card:
                provider, last4 = card.split(":", 1)
                previous_conditions.extend(["t.provider = ?", "t.card_last4 = ?"])
                previous_parameters.extend([provider, last4])
            previous_where = " AND ".join(previous_conditions)
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
            previous_amounts = {row["category"]: float(row["amount"]) for row in previous_rows}
            category_comparison = {"available": previous_count > 0, "previous_month": previous_month}
            categories = with_previous_month_comparison(
                categories,
                previous_transaction_count=previous_count,
                previous_amounts=previous_amounts,
            )

        recent = [dict(row) for row in connection.execute(
            f"""SELECT t.merchant_raw,COALESCE(o.category,t.user_category,t.provider_category,'Needs review') category,
            COALESCE(o.subcategory,t.user_subcategory) subcategory,t.provider,t.card_last4,
            t.transaction_date,t.billing_date,t.billing_month,t.billing_month_source,
            CAST(t.charged_amount AS REAL) amount,{personal_spending_sql()} personal_amount,t.charged_currency,
            a.adjustment_type,a.reimbursed_amount,a.reimbursement_date
            FROM transactions t LEFT JOIN transaction_category_overrides o ON o.transaction_id=t.id
            LEFT JOIN transaction_spending_adjustments a ON a.transaction_id=t.id
            WHERE {where} ORDER BY COALESCE(t.billing_date,t.billing_month||'-01',t.transaction_date) DESC,t.id DESC LIMIT 6""",
            parameters,
        )]

        purchase_activity_summary = None
        if period == "month":
            purchase_conditions = ["t.transaction_date BETWEEN ? AND ?"]
            purchase_parameters: list[object] = [start or "0000-00-00", end or "9999-99-99"]
            if card != "all" and ":" in card:
                provider, last4 = card.split(":", 1)
                purchase_conditions.extend(["t.provider = ?", "t.card_last4 = ?"])
                purchase_parameters.extend([provider, last4])
            purchase_where = " AND ".join(purchase_conditions)
            purchase_rows = connection.execute(
                f"""SELECT t.transaction_date,
                COALESCE(o.category,t.user_category,t.provider_category,'Needs review') category,
                {personal_spending_sql()} personal_amount,t.provider,t.card_last4,
                t.merchant_normalized,t.charged_amount,t.original_amount,t.original_currency,
                t.charged_currency,t.installment_number,t.installment_total
                FROM transactions t LEFT JOIN transaction_category_overrides o ON o.transaction_id=t.id
                WHERE {purchase_where} ORDER BY t.id""",
                purchase_parameters,
            ).fetchall()
            trend, purchase_activity_summary = build_purchase_activity(
                [PurchaseActivityRow(**dict(row)) for row in purchase_rows],
                billed_charges=spent,
                billed_refunds=float(metrics["refunds"]),
            )
        else:
            trend_spending = [dict(row) for row in connection.execute(
                f"""SELECT {REPORTING_MONTH_SQL} bucket,
                ROUND(SUM({personal_spending_sql()})+
                  SUM(CASE WHEN CAST(t.charged_amount AS REAL)<0 THEN CAST(t.charged_amount AS REAL) ELSE 0 END),2) amount
                FROM transactions t WHERE {where} GROUP BY {REPORTING_MONTH_SQL} ORDER BY bucket""",
                parameters,
            )]
            trend_income = {
                row["month"]: float(row["total"])
                for row in connection.execute(
                    """SELECT month,SUM(CAST(amount AS REAL)) total FROM income_entries
                    WHERE month BETWEEN ? AND ? GROUP BY month""",
                    ((start or "0000-00-00")[:7], (end or "9999-99-99")[:7]),
                )
            }
            spending_by_month = {row["bucket"]: float(row["amount"]) for row in trend_spending}
            trend = [
                {
                    "bucket": bucket,
                    "amount": round(spending_by_month.get(bucket, 0), 2),
                    "income": round(trend_income.get(bucket, 0), 2),
                }
                for bucket in sorted(set(spending_by_month) | set(trend_income))
            ]

        uncategorized = connection.execute(
            f"SELECT COUNT(DISTINCT merchant_normalized) FROM transactions WHERE {where} AND user_category IS NULL AND provider_category IS NULL",
            parameters,
        ).fetchone()[0]
        duplicate_rows = connection.execute("SELECT COALESCE(SUM(duplicate_rows),0) FROM imports").fetchone()[0]
        latest_import = connection.execute(
            "SELECT original_name,imported_at,status FROM imports ORDER BY id DESC LIMIT 1"
        ).fetchone()
        largest = connection.execute(
            f"""SELECT merchant_raw,{personal_spending_sql()} amount FROM transactions t
            WHERE {where} AND {personal_spending_sql()}>0 ORDER BY amount DESC LIMIT 1""",
            parameters,
        ).fetchone()
        return {
            "period": {"key": period, "start": start, "end": end, "label": label},
            "selected_card": card,
            "metrics": {
                "spent": round(spent, 2),
                "refunds": round(float(metrics["refunds"]), 2),
                "transactions": int(metrics["transactions"]),
                "daily_average": round(spent / active_days, 2) if active_days else 0,
                "active_days": active_days,
            },
            "income_summary": {
                "has_income": bool(income_row["entries"]),
                "income": balance.income,
                "spending": balance.spending,
                "charges": balance.charges,
                "refunds": balance.refunds,
                "remaining": balance.remaining,
                "remaining_percentage": balance.remaining_percentage,
                "spent_percentage": balance.spent_percentage,
                "scope": "all_cards",
                "averages": {
                    "spending": averages.spending,
                    "amount_left": averages.amount_left,
                    "spending_months": averages.spending_months,
                    "amount_left_months": averages.amount_left_months,
                    "start_month": averages.start_month,
                    "end_month": averages.end_month,
                    "current_month_partial": averages.current_month_partial,
                },
            },
            "cards": cards,
            "categories": categories,
            "category_comparison": category_comparison,
            "recent_transactions": recent,
            "trend": trend,
            "trend_mode": "purchase_activity" if period == "month" else "billing_summary",
            "purchase_activity_summary": purchase_activity_summary,
            "insights": {
                "merchants_needing_review": int(uncategorized),
                "duplicate_rows_prevented": int(duplicate_rows),
                "largest_transaction": dict(largest) if largest else None,
            },
            "latest_import": dict(latest_import) if latest_import else None,
            "available_months": [row[0] for row in connection.execute(
                """SELECT month FROM (
                SELECT DISTINCT COALESCE(billing_month,substr(billing_date,1,7),substr(transaction_date,1,7)) month
                FROM transactions WHERE transaction_date IS NOT NULL OR billing_month IS NOT NULL
                UNION SELECT DISTINCT month FROM income_entries
                ) ORDER BY month DESC"""
            )],
        }
    finally:
        connection.close()
