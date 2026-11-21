"""Bulk database reads for one internally consistent observation snapshot."""

from __future__ import annotations

import json
from datetime import date, datetime
from typing import Any, Iterable

from clearspend.recurring.rules import assess_recurring_series
from clearspend.reporting.periods import resolve_period
from clearspend.reporting.personal_spending import personal_spending_sql
from clearspend.reporting.sql import REPORTING_MONTH_SQL


def observation_scope_inputs(
    connection: Any,
    period: str,
    requested_month: str,
) -> tuple[tuple[str, ...], str | None, str | None, str]:
    """Load coverage once and resolve the requested observation period."""
    rows = connection.execute(
        f"""SELECT report_month FROM (
        SELECT DISTINCT {REPORTING_MONTH_SQL} report_month
        FROM transactions t
        WHERE t.transaction_date IS NOT NULL OR t.billing_month IS NOT NULL
        UNION SELECT DISTINCT month report_month FROM income_entries
        ) coverage WHERE report_month IS NOT NULL ORDER BY report_month"""
    ).fetchall()
    months = tuple(str(row["report_month"]) for row in rows)
    parsed = [datetime.strptime(month, "%Y-%m").date() for month in months]
    today = date.today()
    available = [value for value in parsed if value <= today.replace(day=1)]
    selection = resolve_period(
        period,
        earliest=parsed[0] if parsed else None,
        latest=parsed[-1] if parsed else None,
        latest_available_month=available[-1] if available else None,
        requested_month=requested_month,
    )
    return (
        months,
        selection.start.isoformat() if selection.start else None,
        selection.end.isoformat() if selection.end else None,
        selection.label,
    )


def observation_transaction_history(
    connection: Any,
    card: str,
    end_month: str,
) -> tuple[dict, ...]:
    """Load complete transaction evidence through the observation end month."""
    conditions = [f"{REPORTING_MONTH_SQL}<=?"]
    parameters: list[object] = [end_month or "9999-99"]
    if card != "all" and ":" in card:
        provider, last4 = card.split(":", 1)
        conditions.extend(["t.provider=?", "t.card_last4=?"])
        parameters.extend([provider, last4])
    where = " AND ".join(conditions)
    return tuple(dict(row) for row in connection.execute(
        f"""SELECT t.id,t.merchant_raw,t.merchant_normalized,
        COALESCE(d.canonical_group_id,t.merchant_normalized) canonical_merchant_id,
        COALESCE(d.display_name,t.merchant_raw) merchant_display_name,
        COALESCE(o.category,t.user_category,t.provider_category,'Needs review') category,
        COALESCE(o.subcategory,t.user_subcategory) subcategory,
        COALESCE(t.user_category,t.provider_category,'Needs review') merchant_category,
        CASE WHEN o.transaction_id IS NOT NULL THEN 'transaction_override'
             WHEN t.user_category IS NOT NULL THEN 'merchant_rule'
             WHEN t.provider_category IS NOT NULL THEN 'provider' ELSE 'unmapped' END category_source,
        t.provider,t.card_last4,t.source_sheet,t.transaction_date,t.billing_date,
        t.billing_month,t.billing_month_source,t.installment_number,t.installment_total,
        CAST(t.charged_amount AS NUMERIC) amount,t.charged_currency,
        {personal_spending_sql()} personal_amount,a.adjustment_type,
        CAST(a.reimbursed_amount AS NUMERIC) reimbursed_amount,
        a.reimbursement_date,a.note reimbursement_note,
        CAST(t.original_amount AS NUMERIC) original_amount,t.original_currency,
        t.transaction_type,t.voucher_number,t.notes,t.execution_method,t.exchange_rate,
        e.id event_id,e.name event_name,e.event_type,e.destination event_destination
        FROM transactions t
        LEFT JOIN merchant_display_mappings d
          ON d.merchant_normalized=t.merchant_normalized
        LEFT JOIN transaction_category_overrides o ON o.transaction_id=t.id
        LEFT JOIN transaction_spending_adjustments a ON a.transaction_id=t.id
        LEFT JOIN event_transactions et ON et.transaction_id=t.id
        LEFT JOIN events e ON e.id=et.event_id
        WHERE {where}
        ORDER BY COALESCE(t.billing_date,t.billing_month||'-01',t.transaction_date) DESC,
        t.id DESC""",
        parameters,
    ))


def observation_household_history(connection: Any) -> tuple[dict[str, dict], str]:
    """Load all-card monthly income and net personal spending in one query."""
    rows = connection.execute(
        f"""SELECT 'spending' value_kind,{REPORTING_MONTH_SQL} report_month,
        SUM({personal_spending_sql()})+
        SUM(CASE WHEN CAST(t.charged_amount AS NUMERIC)<0
          THEN CAST(t.charged_amount AS NUMERIC) ELSE 0 END) total
        FROM transactions t GROUP BY {REPORTING_MONTH_SQL}
        UNION ALL
        SELECT 'income' value_kind,month report_month,SUM(CAST(amount AS NUMERIC)) total
        FROM income_entries GROUP BY month"""
    ).fetchall()
    history: dict[str, dict] = {}
    for row in rows:
        month = str(row["report_month"] or "")
        if not month:
            continue
        item = history.setdefault(month, {"bucket": month, "amount": 0.0, "income": 0.0})
        key = "amount" if row["value_kind"] == "spending" else "income"
        item[key] = round(float(row["total"] or 0), 2)
    current_month = date.today().strftime("%Y-%m")
    return history, current_month if current_month in history else ""


def observation_review_keys(connection: Any) -> frozenset[str]:
    rows = connection.execute(
        "SELECT finding_key FROM observation_reviews WHERE active=TRUE"
    ).fetchall()
    return frozenset(str(row["finding_key"]) for row in rows if row["finding_key"])


def _recurring_rows(connection: Any, card: str, end_month: str) -> list[dict]:
    card_sql = ""
    parameters: list[object] = [end_month]
    if card != "all" and ":" in card:
        provider, last4 = card.split(":", 1)
        card_sql = " AND t.provider=? AND t.card_last4=?"
        parameters.extend([provider, last4])
    return [dict(row) for row in connection.execute(
        f"""SELECT COALESCE(d.canonical_group_id,t.merchant_normalized) canonical_group_id,
        COALESCE(d.display_name,p.display_name,t.merchant_raw) display_name,
        t.merchant_raw source_alias,
        COALESCE(o.category,t.user_category,t.provider_category,'Needs review') category,
        {REPORTING_MONTH_SQL} report_month,CAST(t.charged_amount AS NUMERIC) amount,
        p.recurring_type,p.cadence,p.cadence_months,p.lifecycle_status,p.end_month
        FROM transactions t
        LEFT JOIN merchant_display_mappings d ON d.merchant_normalized=t.merchant_normalized
        JOIN recurring_profile_members rpm
          ON rpm.canonical_group_id=COALESCE(d.canonical_group_id,t.merchant_normalized)
         AND rpm.merchant_normalized=t.merchant_normalized AND rpm.included=TRUE
        JOIN recurring_profiles p ON p.canonical_group_id=rpm.canonical_group_id
         AND p.verdict='recurring'
        LEFT JOIN transaction_category_overrides o ON o.transaction_id=t.id
        WHERE CAST(t.charged_amount AS NUMERIC)>0
          AND t.installment_number IS NULL
          AND {REPORTING_MONTH_SQL}<=?{card_sql}
        ORDER BY report_month,t.id""",
        parameters,
    )]


def observation_recurring_by_month(
    connection: Any,
    months: Iterable[str],
    card: str,
) -> dict[str, dict]:
    """Build every monthly recurring input from one history query."""
    selected = tuple(sorted(dict.fromkeys(month for month in months if month)))
    if not selected:
        return {}
    rows = _recurring_rows(connection, card, selected[-1])
    grouped: dict[tuple[str, str], dict] = {}
    for row in rows:
        key = (str(row["canonical_group_id"]), str(row["category"]))
        item = grouped.setdefault(key, {
            "canonical_group_id": row["canonical_group_id"],
            "display_name": row["display_name"],
            "category": row["category"],
            "recurring_type": row["recurring_type"] or "Other recurring",
            "cadence": row["cadence"] or "Unknown",
            "cadence_months": int(row["cadence_months"] or 0),
            "lifecycle_status": row["lifecycle_status"] or "active",
            "end_month": row["end_month"],
            "source_aliases": [],
            "months": {},
        })
        report_month = str(row["report_month"] or "")
        if report_month:
            item["source_aliases"].append((report_month, row["source_alias"]))
            item["months"][report_month] = (
                item["months"].get(report_month, 0.0) + float(row["amount"])
            )

    result: dict[str, dict] = {}
    for current in selected:
        series: list[dict] = []
        for item in grouped.values():
            history = {
                month: amount
                for month, amount in item["months"].items()
                if month <= current
            }
            assessment = assess_recurring_series(
                history,
                period="month",
                start_month=current,
                end_month=current,
                cadence_months=item["cadence_months"],
                lifecycle_status=item["lifecycle_status"],
                end_profile_month=item["end_month"],
                recurring_type=item["recurring_type"],
            )
            if assessment is None:
                continue
            series.append({
                **{name: item[name] for name in (
                    "canonical_group_id", "display_name", "category", "recurring_type",
                    "cadence", "cadence_months", "lifecycle_status", "end_month",
                )},
                "source_aliases": sorted({
                    alias
                    for alias_month, alias in item["source_aliases"]
                    if alias_month <= current
                }),
                "series_id": f"{item['canonical_group_id']}\u0000{item['category']}",
                "amount": assessment.amount,
                "amount_kind": assessment.amount_kind,
                "coverage": assessment.coverage,
                "status": assessment.status,
                "last_billed_month": assessment.last_billed_month,
                "billed_months": len(assessment.scoped_months),
                "typical_amount": assessment.typical_amount,
                "history": list(assessment.history),
            })
        series.sort(key=lambda item: (-(item["amount"] or 0), item["display_name"]))
        result[current] = {
            "period": {"key": "month", "start": f"{current}-01"},
            "selected_card": card,
            "metrics": {"active_series": len(series)},
            "series": series,
        }
    return result


def observation_installments_by_month(
    connection: Any,
    months: Iterable[str],
    card: str,
) -> dict[str, dict]:
    selected = tuple(sorted(dict.fromkeys(month for month in months if month)))
    if not selected:
        return {}
    placeholders = ",".join("?" for _ in selected)
    card_sql = ""
    parameters: list[object] = [*selected]
    if card != "all" and ":" in card:
        provider, last4 = card.split(":", 1)
        card_sql = " AND t.provider=? AND t.card_last4=?"
        parameters.extend([provider, last4])
    rows = [dict(row) for row in connection.execute(
        f"""SELECT t.provider,t.card_last4,
        COALESCE(d.canonical_group_id,t.merchant_normalized) canonical_merchant_id,
        COALESCE(d.display_name,t.merchant_raw) display_name,
        t.merchant_raw source_alias,t.transaction_date,t.original_amount,
        t.original_currency,t.installment_total,{REPORTING_MONTH_SQL} report_month,
        CAST(t.charged_amount AS NUMERIC) amount
        FROM transactions t
        LEFT JOIN merchant_display_mappings d
          ON d.merchant_normalized=t.merchant_normalized
        WHERE t.installment_number IS NOT NULL
          AND CAST(t.charged_amount AS NUMERIC)>0
          AND {REPORTING_MONTH_SQL} IN ({placeholders}){card_sql}
        ORDER BY report_month,t.id""",
        parameters,
    )]
    result = {
        month: {"installment_billed": 0.0, "plans": {}}
        for month in selected
    }
    for row in rows:
        month = str(row["report_month"])
        payload = result[month]
        payload["installment_billed"] += float(row["amount"] or 0)
        plan_id = json.dumps([
            row.get("provider") or "", row.get("card_last4") or "",
            row.get("canonical_merchant_id") or "", row.get("transaction_date") or "",
            str(row.get("original_amount") or ""), row.get("original_currency") or "",
            int(row.get("installment_total") or 0),
        ], ensure_ascii=False, separators=(",", ":"))
        payload["plans"].setdefault(plan_id, {
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
