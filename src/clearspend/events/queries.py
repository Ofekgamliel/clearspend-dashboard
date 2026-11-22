"""Read models for projects and events."""

from __future__ import annotations

from collections import defaultdict

from clearspend.database.connection import DatabaseTarget, database_connection
from clearspend.events.rules import summarize_event_transactions
from clearspend.reporting.personal_spending import personal_spending_sql
from clearspend.reporting.queries import period_bounds


def events_payload(
    database: DatabaseTarget, period: str, card: str, month: str = "",
) -> dict:
    with database_connection(database) as connection:
        start, end, label = period_bounds(connection, period, month)
        all_event_rows = connection.execute(
            """SELECT id,name,event_type,destination,icon,start_date,end_date,status,budget,notes
            FROM events WHERE status!='cancelled' ORDER BY start_date DESC,name"""
        ).fetchall()
        available_fields = (
            "id", "name", "event_type", "destination", "icon",
            "start_date", "end_date", "status",
        )
        available_events = [
            {field: row[field] for field in available_fields}
            for row in all_event_rows
        ]
        event_rows = [
            row for row in all_event_rows
            if start is not None and end is not None
            and row["start_date"] <= end and row["end_date"] >= start
        ]

        transactions_by_event: dict[str, list[dict]] = defaultdict(list)
        if event_rows:
            event_ids = [row["id"] for row in event_rows]
            placeholders = ",".join("?" for _event_id in event_ids)
            conditions = [f"et.event_id IN ({placeholders})"]
            parameters: list[object] = list(event_ids)
            if card != "all" and ":" in card:
                provider, last4 = card.split(":", 1)
                conditions.extend(["t.provider=?", "t.card_last4=?"])
                parameters.extend([provider, last4])
            where = " AND ".join(conditions)
            transaction_rows = connection.execute(
                f"""SELECT et.event_id,t.id,t.merchant_raw,
                COALESCE(d.display_name,t.merchant_raw) merchant_display_name,
                COALESCE(o.category,t.user_category,t.provider_category,'Needs review') category,
                t.transaction_date,t.provider,t.card_last4,
                CAST(t.charged_amount AS NUMERIC) amount,
                {personal_spending_sql()} personal_amount
                FROM event_transactions et JOIN transactions t ON t.id=et.transaction_id
                LEFT JOIN merchant_display_mappings d ON d.merchant_normalized=t.merchant_normalized
                LEFT JOIN transaction_category_overrides o ON o.transaction_id=t.id
                WHERE {where}
                ORDER BY et.event_id,t.transaction_date DESC,t.id DESC""",
                parameters,
            ).fetchall()
            for row in transaction_rows:
                transaction = dict(row)
                event_id = transaction.pop("event_id")
                transactions_by_event[event_id].append(transaction)

        events = []
        for event_row in event_rows:
            transactions = transactions_by_event[event_row["id"]]
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
