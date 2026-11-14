"""Application workflow for reversible observation-review decisions."""

from __future__ import annotations

import json
import re
from datetime import date, datetime
from pathlib import Path

from clearspend.database.connection import connect_database
from clearspend.observations.policy import OBSERVATION_RESOLUTIONS


def save_observation_review(
    database: Path,
    finding_key: str,
    observation_type: str,
    resolution: str,
    month: str,
    transaction_ids: object,
    recurring_series_id: str = "",
    occurrence_start: str = "",
    occurrence_end: str = "",
    merchant_label: str = "",
    remove: bool = False,
) -> dict:
    finding_key = finding_key.strip()
    observation_type = observation_type.strip().upper()
    resolution = resolution.strip()
    month = month.strip()
    recurring_series_id = recurring_series_id.strip()
    occurrence_start = occurrence_start.strip()
    occurrence_end = occurrence_end.strip()
    merchant_label = merchant_label.strip()
    expected_resolution = OBSERVATION_RESOLUTIONS.get(observation_type)
    if not expected_resolution:
        raise ValueError("This observation type cannot be resolved")
    if (
        not finding_key
        or len(finding_key) > 1000
        or not finding_key.startswith(f"{observation_type}:")
    ):
        raise ValueError("A valid finding key is required")
    if resolution != expected_resolution:
        raise ValueError("Invalid resolution for this observation type")
    if not re.fullmatch(r"\d{4}-\d{2}", month):
        raise ValueError("A valid observation month is required")
    if not isinstance(transaction_ids, list):
        raise ValueError("Transaction IDs must be a list")
    try:
        ids = sorted({int(value) for value in transaction_ids if int(value) > 0})
    except (TypeError, ValueError) as error:
        raise ValueError("Transaction IDs must be positive integers") from error
    if observation_type == "POSSIBLE DUPLICATE" and len(ids) < 2:
        raise ValueError("A duplicate review requires at least two transactions")
    if observation_type == "UNUSUAL TRANSACTION" and len(ids) != 1:
        raise ValueError("An unusual-transaction review requires one transaction")
    if (
        observation_type == "ADDITIONAL RECURRING CHARGE"
        and (len(ids) < 2 or not recurring_series_id)
    ):
        raise ValueError("A recurring-charge review requires its series and transactions")
    for value in (occurrence_start, occurrence_end):
        if value:
            try:
                date.fromisoformat(value)
            except ValueError as error:
                raise ValueError("Occurrence dates must be valid dates") from error
    connection = connect_database(database)
    try:
        if ids:
            placeholders = ",".join("?" for _ in ids)
            found = connection.execute(
                f"SELECT COUNT(*) FROM transactions WHERE id IN ({placeholders})", ids
            ).fetchone()[0]
            if found != len(ids):
                raise ValueError("One or more reviewed transactions were not found")
        now = datetime.now().astimezone().isoformat()
        if remove:
            changed = connection.execute(
                """UPDATE observation_reviews SET active=0,updated_at=?
                WHERE finding_key=? AND active=1""",
                (now, finding_key),
            ).rowcount
            connection.commit()
            return {"status": "restored", "finding_key": finding_key, "changed": bool(changed)}
        connection.execute(
            """INSERT INTO observation_reviews(
            finding_key,observation_type,resolution,month,transaction_ids,recurring_series_id,
            occurrence_start,occurrence_end,merchant_label,active,reviewed_at,updated_at
            ) VALUES(?,?,?,?,?,?,?,?,?,1,?,?)
            ON CONFLICT(finding_key) DO UPDATE SET
            observation_type=excluded.observation_type,resolution=excluded.resolution,
            month=excluded.month,transaction_ids=excluded.transaction_ids,
            recurring_series_id=excluded.recurring_series_id,
            occurrence_start=excluded.occurrence_start,occurrence_end=excluded.occurrence_end,
            merchant_label=excluded.merchant_label,active=1,updated_at=excluded.updated_at""",
            (
                finding_key, observation_type, resolution, month,
                json.dumps(ids, separators=(",", ":")), recurring_series_id or None,
                occurrence_start or None, occurrence_end or None, merchant_label or None,
                now, now,
            ),
        )
        connection.commit()
        return {"status": "reviewed", "finding_key": finding_key, "resolution": resolution}
    finally:
        connection.close()
