"""Read models for projects and events."""

from __future__ import annotations

from pathlib import Path

from clearspend.database.connection import connect_database
from clearspend.events.rules import summarize_event_transactions
from clearspend.reporting.personal_spending import personal_spending_sql
from clearspend.reporting.queries import period_bounds


def events_payload(database: Path, period: str, card: str, month: str = "") -> dict:
    connection = connect_database(database)
    try:
        start, end, label = period_bounds(connection, period, month)
        event_rows = connection.execute(
            """SELECT id,name,event_type,destination,icon,start_date,end_date,status,budget,notes
            FROM events WHERE status!='cancelled' AND start_date<=? AND end_date>=?
            ORDER BY start_date DESC,name""",
            (end, start),
        ).fetchall()
        available_events = [dict(row) for row in connection.execute(
            """SELECT id,name,event_type,destination,icon,start_date,end_date,status
            FROM events ORDER BY start_date DESC,name"""
        )]
        events = []
        for event_row in event_rows:
            conditions = ["et.event_id=?"]
            parameters: list[object] = [event_row["id"]]
            if card != "all" and ":" in card:
                provider, last4 = card.split(":", 1)
                conditions.extend(["t.provider=?", "t.card_last4=?"])
                parameters.extend([provider, last4])
            where = " AND ".join(conditions)
            transactions = [dict(row) for row in connection.execute(
                f"""SELECT t.id,t.merchant_raw,
                COALESCE(d.display_name,t.merchant_raw) merchant_display_name,
                COALESCE(o.category,t.user_category,t.provider_category,'Needs review') category,
                t.transaction_date,t.provider,t.card_last4,
                CAST(t.charged_amount AS REAL) amount,{personal_spending_sql()} personal_amount
                FROM event_transactions et JOIN transactions t ON t.id=et.transaction_id
                LEFT JOIN merchant_display_mappings d ON d.merchant_normalized=t.merchant_normalized
                LEFT JOIN transaction_category_overrides o ON o.transaction_id=t.id
                WHERE {where} ORDER BY t.transaction_date DESC,t.id DESC""",
                parameters,
            )]
            if card != "all" and not transactions:
                continue
            summary = summarize_event_transactions(
                transactions, period_start=start, period_end=end
            )
            item = dict(event_row)
            item["transactions"] = transactions
            item.update({
                "transaction_count": summary.transaction_count,
                "amount": summary.amount,
                "total_transaction_count": summary.total_transaction_count,
                "total_amount": summary.total_amount,
                "category_count": summary.category_count,
                "card_count": summary.card_count,
            })
            events.append(item)
        return {
            "period": {"key": period, "start": start, "end": end, "label": label},
            "selected_card": card,
            "events": events,
            "available_events": available_events,
        }
    finally:
        connection.close()
