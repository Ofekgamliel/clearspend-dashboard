"""Read models for transaction browsing, filtering, and complete-history search."""

from __future__ import annotations

from pathlib import Path

from clearspend.database.connection import connect_database
from clearspend.reporting.personal_spending import personal_spending_sql
from clearspend.reporting.queries import filtered_where


def transactions_payload(
    database: Path,
    period: str,
    card: str,
    search: str = "",
    month: str = "",
    category: str = "",
    event_scope: str = "all",
) -> dict:
    connection = connect_database(database)
    try:
        where, parameters, period_data = filtered_where(
            connection, period, card, month, event_scope
        )
        if search.strip():
            where += """ AND (
                t.merchant_raw LIKE ? OR t.merchant_normalized LIKE ? OR
                COALESCE(d.display_name,'') LIKE ? OR
                COALESCE(o.category,t.user_category,t.provider_category,'Needs review') LIKE ?
            )"""
            term = f"%{search.strip()}%"
            parameters.extend([term, term, term, term])
        if category.strip():
            where += " AND COALESCE(o.category,t.user_category,t.provider_category,'Needs review') = ?"
            parameters.append(category.strip())
        total = connection.execute(
            f"""SELECT COUNT(*) FROM transactions t
            LEFT JOIN merchant_display_mappings d ON d.merchant_normalized=t.merchant_normalized
            LEFT JOIN transaction_category_overrides o ON o.transaction_id=t.id WHERE {where}""",
            parameters,
        ).fetchone()[0]
        row_limit = "" if search.strip() else "LIMIT 1000"
        rows = [dict(row) for row in connection.execute(
            f"""SELECT t.id,t.merchant_raw,t.merchant_normalized,
            COALESCE(d.canonical_group_id,t.merchant_normalized) canonical_merchant_id,
            COALESCE(d.display_name,t.merchant_raw) merchant_display_name,
            COALESCE(o.category,t.user_category,t.provider_category,'Needs review') category,
            COALESCE(o.subcategory,t.user_subcategory) subcategory,
            COALESCE(t.user_category,t.provider_category,'Needs review') merchant_category,
            CASE WHEN o.transaction_id IS NOT NULL THEN 'transaction_override'
                 WHEN t.user_category IS NOT NULL THEN 'merchant_rule'
                 WHEN t.provider_category IS NOT NULL THEN 'provider' ELSE 'unmapped' END category_source,
            provider,card_last4,source_sheet,transaction_date,billing_date,
            billing_month,billing_month_source,installment_number,installment_total,
            CAST(charged_amount AS REAL) amount,charged_currency,
            {personal_spending_sql()} personal_amount,a.adjustment_type,
            CAST(a.reimbursed_amount AS REAL) reimbursed_amount,
            a.reimbursement_date,a.note reimbursement_note,
            CAST(original_amount AS REAL) original_amount,original_currency,
            t.transaction_type,t.voucher_number,t.notes,t.execution_method,t.exchange_rate,
            e.id event_id,e.name event_name,e.event_type,e.destination event_destination
            FROM transactions t LEFT JOIN merchant_display_mappings d
              ON d.merchant_normalized=t.merchant_normalized
            LEFT JOIN transaction_category_overrides o ON o.transaction_id=t.id
            LEFT JOIN transaction_spending_adjustments a ON a.transaction_id=t.id
            LEFT JOIN event_transactions et ON et.transaction_id=t.id
            LEFT JOIN events e ON e.id=et.event_id
            WHERE {where}
            ORDER BY COALESCE(billing_date,billing_month||'-01',transaction_date) DESC,t.id DESC
            {row_limit}""",
            parameters,
        )]
        return {
            "period": period_data,
            "selected_card": card,
            "event_scope": event_scope,
            "total": int(total),
            "transactions": rows,
        }
    finally:
        connection.close()
