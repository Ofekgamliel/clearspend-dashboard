"""Database-backed reporting coverage queries."""

from __future__ import annotations

import sqlite3
from datetime import date, datetime

from clearspend.reporting.periods import resolve_period
from clearspend.reporting.scope import build_reporting_filter
from clearspend.reporting.sql import REPORTING_MONTH_SQL


def period_bounds(
    connection: sqlite3.Connection,
    period: str,
    month: str = "",
    *,
    today: date | None = None,
) -> tuple[str | None, str | None, str]:
    """Resolve reporting bounds from transaction and income coverage."""

    row = connection.execute(
        """SELECT MAX(value) FROM (
        SELECT COALESCE(billing_month,substr(billing_date,1,7),substr(transaction_date,1,7))||'-01' value
        FROM transactions WHERE transaction_date IS NOT NULL OR billing_month IS NOT NULL
        UNION ALL SELECT month||'-01' value FROM income_entries
        )"""
    ).fetchone()
    latest = datetime.strptime(row[0], "%Y-%m-%d").date() if row and row[0] else None
    latest_available = None
    earliest = None
    if period == "month":
        latest_available_value = connection.execute(
            """SELECT MAX(value) FROM (
            SELECT COALESCE(billing_month,substr(billing_date,1,7),substr(transaction_date,1,7))||'-01' value
            FROM transactions WHERE transaction_date IS NOT NULL OR billing_month IS NOT NULL
            UNION ALL SELECT month||'-01' value FROM income_entries
            ) WHERE value<=?""",
            ((today or date.today()).isoformat(),),
        ).fetchone()[0]
        latest_available = (
            datetime.strptime(latest_available_value, "%Y-%m-%d").date()
            if latest_available_value else None
        )
    elif period != "year":
        earliest_value = connection.execute(
            """SELECT MIN(value) FROM (
            SELECT COALESCE(billing_month,substr(billing_date,1,7),substr(transaction_date,1,7))||'-01' value
            FROM transactions WHERE transaction_date IS NOT NULL OR billing_month IS NOT NULL
            UNION ALL SELECT month||'-01' value FROM income_entries
            )"""
        ).fetchone()[0]
        earliest = datetime.strptime(earliest_value, "%Y-%m-%d").date() if earliest_value else None
    selection = resolve_period(
        period,
        earliest=earliest,
        latest=latest,
        latest_available_month=latest_available,
        requested_month=month,
    )
    return (
        selection.start.isoformat() if selection.start else None,
        selection.end.isoformat() if selection.end else None,
        selection.label,
    )


def filtered_where(
    connection: sqlite3.Connection,
    period: str,
    card: str,
    month: str = "",
    event_scope: str = "all",
) -> tuple[str, list[object], dict]:
    """Build the established transaction/reporting filter from database coverage."""

    start, end, label = period_bounds(connection, period, month)
    reporting_filter = build_reporting_filter(
        REPORTING_MONTH_SQL,
        start=start,
        end=end,
        card=card,
        event_scope=event_scope,
    )
    return reporting_filter.where, list(reporting_filter.parameters), {
        "key": period, "start": start, "end": end, "label": label,
    }
