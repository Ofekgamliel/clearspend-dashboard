"""Read-model assembly for recurring payments and installment commitments."""

from __future__ import annotations

from datetime import date
from pathlib import Path

from clearspend.database.connection import connect_database
from clearspend.recurring.rules import assess_recurring_series, median, month_history
from clearspend.reporting.queries import period_bounds
from clearspend.reporting.sql import REPORTING_MONTH_SQL


def recurring_payload(
    database: Path, period: str, card: str, month: str = "",
) -> dict:
    connection = connect_database(database)
    try:
        start, end, label = period_bounds(connection, period, month)
        start_month = (start or "0000-00")[:7]
        end_month = (end or date.today().isoformat())[:7]
        card_sql = ""
        card_parameters: list[object] = []
        if card != "all" and ":" in card:
            provider, last4 = card.split(":", 1)
            card_sql = " AND t.provider=? AND t.card_last4=?"
            card_parameters = [provider, last4]

        transaction_rows = connection.execute(
            f"""SELECT COALESCE(d.canonical_group_id,t.merchant_normalized) canonical_group_id,
            COALESCE(d.display_name,p.display_name,t.merchant_raw) display_name,
            t.merchant_raw source_alias,
            COALESCE(o.category,t.user_category,t.provider_category,'Needs review') category,
            {REPORTING_MONTH_SQL} report_month,CAST(t.charged_amount AS REAL) amount,
            p.recurring_type,p.cadence,p.cadence_months,p.lifecycle_status,p.end_month
            FROM transactions t
            LEFT JOIN merchant_display_mappings d ON d.merchant_normalized=t.merchant_normalized
            JOIN recurring_profile_members rpm
              ON rpm.canonical_group_id=COALESCE(d.canonical_group_id,t.merchant_normalized)
             AND rpm.merchant_normalized=t.merchant_normalized AND rpm.included=1
            JOIN recurring_profiles p ON p.canonical_group_id=rpm.canonical_group_id
             AND p.verdict='recurring'
            LEFT JOIN transaction_category_overrides o ON o.transaction_id=t.id
            WHERE CAST(t.charged_amount AS REAL)>0 AND t.installment_number IS NULL
              AND {REPORTING_MONTH_SQL}<=?{card_sql}
            ORDER BY report_month,t.id""",
            [end_month, *card_parameters],
        ).fetchall()
        grouped: dict[tuple[str, str], dict] = {}
        for row in transaction_rows:
            key = (row["canonical_group_id"], row["category"])
            item = grouped.setdefault(key, {
                "canonical_group_id": row["canonical_group_id"],
                "display_name": row["display_name"], "category": row["category"],
                "recurring_type": row["recurring_type"] or "Other recurring",
                "cadence": row["cadence"] or "Unknown",
                "cadence_months": int(row["cadence_months"] or 0),
                "lifecycle_status": row["lifecycle_status"] or "active",
                "end_month": row["end_month"], "months": {}, "source_aliases": set(),
            })
            item["source_aliases"].add(row["source_alias"])
            report_month = row["report_month"]
            if report_month:
                item["months"][report_month] = (
                    item["months"].get(report_month, 0.0) + float(row["amount"])
                )

        series: list[dict] = []
        trend_totals: dict[str, float] = {}
        for item in grouped.values():
            months = item["months"]
            assessment = assess_recurring_series(
                months,
                period=period,
                start_month=start_month,
                end_month=end_month,
                cadence_months=item["cadence_months"],
                lifecycle_status=item["lifecycle_status"],
                end_profile_month=item["end_month"],
                recurring_type=item["recurring_type"],
            )
            if assessment is None:
                continue
            row = {
                **{key: item[key] for key in (
                    "canonical_group_id", "display_name", "category", "recurring_type",
                    "cadence", "cadence_months", "lifecycle_status", "end_month",
                )},
                "source_aliases": sorted(item["source_aliases"]),
                "series_id": f"{item['canonical_group_id']}\u0000{item['category']}",
                "amount": assessment.amount,
                "amount_kind": assessment.amount_kind,
                "coverage": assessment.coverage,
                "status": assessment.status,
                "last_billed_month": assessment.last_billed_month,
                "billed_months": len(assessment.scoped_months),
                "typical_amount": assessment.typical_amount,
                "history": list(assessment.history),
            }
            series.append(row)
            for current, value in months.items():
                if start_month <= current <= end_month:
                    trend_totals[current] = trend_totals.get(current, 0.0) + value

        series.sort(key=lambda item: (-(item["amount"] or 0), item["display_name"]))

        installment_rows = connection.execute(
            f"""SELECT t.provider,t.card_last4,
            COALESCE(d.canonical_group_id,t.merchant_normalized) canonical_group_id,
            COALESCE(d.display_name,t.merchant_raw) display_name,t.merchant_raw source_alias,
            COALESCE(o.category,t.user_category,t.provider_category,'Needs review') category,
            t.transaction_date,t.original_amount,t.installment_number,t.installment_total,
            {REPORTING_MONTH_SQL} report_month,CAST(t.charged_amount AS REAL) amount
            FROM transactions t
            LEFT JOIN merchant_display_mappings d ON d.merchant_normalized=t.merchant_normalized
            LEFT JOIN transaction_category_overrides o ON o.transaction_id=t.id
            WHERE CAST(t.charged_amount AS REAL)>0 AND t.installment_number IS NOT NULL
              AND {REPORTING_MONTH_SQL}<=?{card_sql} ORDER BY report_month,t.id""",
            [end_month, *card_parameters],
        ).fetchall()
        plans: dict[tuple, dict] = {}
        for row in installment_rows:
            key = (
                row["provider"], row["card_last4"], row["canonical_group_id"],
                row["transaction_date"], row["original_amount"], row["installment_total"],
            )
            plan = plans.setdefault(key, {
                "display_name": row["display_name"], "source_alias": row["source_alias"],
                "category": row["category"], "total": int(row["installment_total"] or 0),
                "rows": [],
            })
            plan["rows"].append(dict(row))
        commitments: list[dict] = []
        for plan in plans.values():
            scoped = [
                row for row in plan["rows"]
                if start_month <= row["report_month"] <= end_month
            ]
            if not scoped:
                continue
            current = max(int(row["installment_number"] or 0) for row in plan["rows"])
            paid = sum(float(row["amount"]) for row in plan["rows"])
            charge = median([float(row["amount"]) for row in plan["rows"]])
            remaining_count = max(plan["total"] - current, 0)
            history_amounts: dict[str, float] = {}
            for row in plan["rows"]:
                history_amounts[row["report_month"]] = (
                    history_amounts.get(row["report_month"], 0.0) + float(row["amount"])
                )
            commitments.append({
                "display_name": plan["display_name"], "source_alias": plan["source_alias"],
                "category": plan["category"], "progress": f"{current} / {plan['total']}",
                "current_installment": current, "total_installments": plan["total"],
                "charge": round(charge, 2), "paid": round(paid, 2),
                "remaining": round(remaining_count * charge, 2),
                "remaining_count": remaining_count,
                "status": "active" if remaining_count else "completed",
                "history": month_history(history_amounts, end_month, 0),
            })
        commitments.sort(key=lambda item: (-item["remaining"], item["display_name"]))

        recurring_billed = round(sum(
            sum(
                float(row["amount"])
                for row in transaction_rows
                if row["canonical_group_id"] == item["canonical_group_id"]
                and row["category"] == item["category"]
                and start_month <= row["report_month"] <= end_month
            )
            for item in series
        ), 2)
        installment_billed = round(sum(
            float(row["amount"])
            for row in installment_rows
            if start_month <= row["report_month"] <= end_month
        ), 2)
        month_count = max(len({
            row["report_month"] for row in connection.execute(
                f"SELECT {REPORTING_MONTH_SQL} report_month FROM transactions t "
                f"WHERE {REPORTING_MONTH_SQL} BETWEEN ? AND ?{card_sql}",
                [start_month, end_month, *card_parameters],
            ) if row["report_month"]
        }), 1)
        spending = float(connection.execute(
            f"SELECT COALESCE(SUM(CASE WHEN CAST(t.charged_amount AS REAL)>0 "
            f"THEN CAST(t.charged_amount AS REAL) ELSE 0 END),0) FROM transactions t "
            f"WHERE {REPORTING_MONTH_SQL} BETWEEN ? AND ?{card_sql}",
            [start_month, end_month, *card_parameters],
        ).fetchone()[0])
        verdicts = connection.execute(
            """SELECT SUM(review_count) reviewed,
            SUM(CASE WHEN verdict='recurring' THEN review_count ELSE 0 END) recurring,
            SUM(CASE WHEN verdict='not_recurring' THEN review_count ELSE 0 END) not_recurring
            FROM recurring_profiles"""
        ).fetchone()
        attention = sum(
            item["status"] in {"missing", "increased", "due", "overdue", "unknown"}
            for item in series
        )
        recurring_average = recurring_billed if period == "month" else recurring_billed / month_count
        installment_average = (
            installment_billed if period == "month" else installment_billed / month_count
        )
        return {
            "period": {"key": period, "start": start, "end": end, "label": label},
            "selected_card": card,
            "metrics": {
                "recurring_billed": recurring_billed,
                "recurring_average": round(recurring_average, 2),
                "active_series": len(series), "needs_attention": attention,
                "installment_billed": installment_billed,
                "installment_average": round(installment_average, 2),
                "installment_plans": len(commitments),
                "recurring_share": round(recurring_billed / spending * 100, 1) if spending else 0,
                "installment_share": round(installment_billed / spending * 100, 1) if spending else 0,
            },
            "series": series, "commitments": commitments,
            "trend": [
                {"month": current, "amount": round(value, 2)}
                for current, value in sorted(trend_totals.items())
            ],
            "verdict_summary": {
                "reviewed": int(verdicts["reviewed"] or 0),
                "recurring": int(verdicts["recurring"] or 0),
                "not_recurring": int(verdicts["not_recurring"] or 0),
                "unresolved": 0,
            },
        }
    finally:
        connection.close()
