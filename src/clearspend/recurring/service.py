"""Application workflows for reviewed recurring profiles and alias membership."""

from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path

from clearspend.database.connection import connect_database
from clearspend.recurring.rules import (
    ALLOWED_RECURRING_TYPES,
    CADENCE_MONTHS,
    LIFECYCLE_STATUSES,
)


def save_recurring_profile(
    database: Path,
    canonical_group_id: str,
    recurring_type: str,
    cadence: str,
    lifecycle_status: str,
    end_month: str,
) -> dict:
    canonical_group_id = canonical_group_id.strip()
    lifecycle_status = lifecycle_status.strip().lower()
    if not canonical_group_id:
        raise ValueError("A recurring profile is required")
    if recurring_type not in ALLOWED_RECURRING_TYPES:
        raise ValueError("Invalid recurring type")
    if cadence not in CADENCE_MONTHS:
        raise ValueError("Invalid cadence")
    if lifecycle_status not in LIFECYCLE_STATUSES:
        raise ValueError("Invalid lifecycle status")
    end_month = end_month.strip()
    if (
        lifecycle_status == "ended"
        and end_month
        and not re.fullmatch(r"\d{4}-(0[1-9]|1[0-2])", end_month)
    ):
        raise ValueError("End month must use YYYY-MM")
    if lifecycle_status != "ended":
        end_month = ""
    connection = connect_database(database)
    try:
        existing = connection.execute(
            "SELECT * FROM recurring_profiles WHERE canonical_group_id=? AND verdict='recurring'",
            (canonical_group_id,),
        ).fetchone()
        if not existing:
            raise ValueError("Recurring profile was not found")
        connection.execute(
            """UPDATE recurring_profiles SET recurring_type=?,cadence=?,cadence_months=?,
            lifecycle_status=?,end_month=?,updated_at=? WHERE canonical_group_id=?""",
            (recurring_type, cadence, CADENCE_MONTHS[cadence], lifecycle_status,
             end_month or None, datetime.now().isoformat(timespec="seconds"), canonical_group_id),
        )
        connection.commit()
        return dict(connection.execute(
            "SELECT * FROM recurring_profiles WHERE canonical_group_id=?", (canonical_group_id,)
        ).fetchone())
    finally:
        connection.close()


def manage_recurring_profile(
    database: Path,
    canonical_group_id: str,
    verdict: str,
    recurring_type: str = "",
    cadence: str = "",
    lifecycle_status: str = "active",
    end_month: str = "",
    included_aliases: list[str] | None = None,
) -> dict:
    canonical_group_id = canonical_group_id.strip()
    verdict = verdict.strip()
    recurring_type = recurring_type.strip()
    cadence = cadence.strip()
    lifecycle_status = lifecycle_status.strip().lower()
    end_month = end_month.strip()
    if not canonical_group_id:
        raise ValueError("A merchant group is required")
    if verdict not in {"recurring", "not_recurring"}:
        raise ValueError("Invalid recurring verdict")
    if verdict == "recurring":
        if recurring_type not in ALLOWED_RECURRING_TYPES:
            raise ValueError("Invalid recurring type")
        if cadence not in CADENCE_MONTHS:
            raise ValueError("Invalid cadence")
        if lifecycle_status not in LIFECYCLE_STATUSES:
            raise ValueError("Invalid lifecycle status")
        if lifecycle_status == "ended" and not end_month:
            raise ValueError("An end month is required for an ended profile")
        if end_month and not re.fullmatch(r"\d{4}-(0[1-9]|1[0-2])", end_month):
            raise ValueError("End month must use YYYY-MM")
        if lifecycle_status != "ended":
            end_month = ""
    connection = connect_database(database)
    try:
        merchant_rows = connection.execute(
            """SELECT DISTINCT t.merchant_normalized,
            COALESCE(d.display_name,t.merchant_raw) display_name
            FROM transactions t
            LEFT JOIN merchant_display_mappings d ON d.merchant_normalized=t.merchant_normalized
            WHERE COALESCE(d.canonical_group_id,t.merchant_normalized)=?
            ORDER BY t.merchant_normalized""",
            (canonical_group_id,),
        ).fetchall()
        if not merchant_rows:
            raise ValueError("Merchant group was not found")
        merchant = merchant_rows[0]
        available_aliases = {row["merchant_normalized"] for row in merchant_rows}
        if included_aliases is None:
            selected_aliases = set(available_aliases)
        else:
            selected_aliases = {
                str(alias).strip() for alias in included_aliases if str(alias).strip()
            }
            if not selected_aliases.issubset(available_aliases):
                raise ValueError("A recurring alias does not belong to this merchant group")
        if verdict == "recurring" and not selected_aliases:
            raise ValueError("Select at least one original merchant name for recurring tracking")
        existing = connection.execute(
            "SELECT * FROM recurring_profiles WHERE canonical_group_id=?",
            (canonical_group_id,),
        ).fetchone()
        now = datetime.now().astimezone().isoformat()
        if verdict == "not_recurring":
            if existing:
                connection.execute(
                    """UPDATE recurring_profiles SET verdict='not_recurring',display_name=?,updated_at=?
                    WHERE canonical_group_id=?""",
                    (merchant["display_name"], now, canonical_group_id),
                )
            else:
                connection.execute(
                    """INSERT INTO recurring_profiles(
                    canonical_group_id,display_name,verdict,lifecycle_status,updated_at
                    ) VALUES(?,?,'not_recurring','active',?)""",
                    (canonical_group_id, merchant["display_name"], now),
                )
            selected_aliases = set()
        else:
            connection.execute(
                """INSERT INTO recurring_profiles(
                canonical_group_id,display_name,verdict,recurring_type,cadence,cadence_months,
                lifecycle_status,end_month,updated_at
                ) VALUES(?,?,'recurring',?,?,?,?,?,?)
                ON CONFLICT(canonical_group_id) DO UPDATE SET
                display_name=excluded.display_name,verdict='recurring',
                recurring_type=excluded.recurring_type,cadence=excluded.cadence,
                cadence_months=excluded.cadence_months,
                lifecycle_status=excluded.lifecycle_status,end_month=excluded.end_month,
                updated_at=excluded.updated_at""",
                (canonical_group_id, merchant["display_name"], recurring_type, cadence,
                 CADENCE_MONTHS[cadence], lifecycle_status, end_month or None, now),
            )
        for alias in available_aliases:
            connection.execute(
                """INSERT INTO recurring_profile_members(
                canonical_group_id,merchant_normalized,included,updated_at
                ) VALUES(?,?,?,?)
                ON CONFLICT(canonical_group_id,merchant_normalized) DO UPDATE SET
                included=excluded.included,updated_at=excluded.updated_at""",
                (canonical_group_id, alias, int(alias in selected_aliases), now),
            )
        connection.commit()
        result = dict(connection.execute(
            "SELECT * FROM recurring_profiles WHERE canonical_group_id=?",
            (canonical_group_id,),
        ).fetchone())
        result["included_aliases"] = sorted(selected_aliases)
        return result
    finally:
        connection.close()
