"""Read models for persisted observation-review decisions."""

from __future__ import annotations

import json
from pathlib import Path

from clearspend.database.connection import connect_database


def observation_reviews_payload(database: Path) -> dict:
    connection = connect_database(database)
    try:
        rows = connection.execute(
            """SELECT finding_key,observation_type,resolution,month,transaction_ids,
            recurring_series_id,occurrence_start,occurrence_end,merchant_label,reviewed_at,updated_at
            FROM observation_reviews WHERE active=1 ORDER BY updated_at DESC"""
        ).fetchall()
        reviews = []
        for row in rows:
            item = dict(row)
            try:
                item["transaction_ids"] = json.loads(item["transaction_ids"] or "[]")
            except json.JSONDecodeError:
                item["transaction_ids"] = []
            reviews.append(item)
        return {"reviews": reviews}
    finally:
        connection.close()
