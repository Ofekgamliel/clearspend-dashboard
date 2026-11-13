from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta


@dataclass(frozen=True)
class PeriodSelection:
    start: date | None
    end: date | None
    label: str


def add_months(value: date, count: int) -> date:
    """Shift to the first day of a calendar month."""
    number = value.year * 12 + value.month - 1 + count
    year, month_zero = divmod(number, 12)
    return date(year, month_zero + 1, 1)


def month_number(value: str) -> int:
    year, month = (int(part) for part in value.split("-", 1))
    return year * 12 + month - 1


def shift_month(value: str, count: int) -> str:
    number = month_number(value) + count
    return f"{number // 12:04d}-{number % 12 + 1:02d}"


def resolve_period(
    period: str,
    *,
    earliest: date | None,
    latest: date | None,
    latest_available_month: date | None = None,
    requested_month: str = "",
) -> PeriodSelection:
    """Resolve a UI period using already-discovered data coverage dates.

    ``latest_available_month`` is the latest month not beyond today. It keeps
    future-dated statement rows from becoming the default month while still
    allowing an explicitly requested future month.
    """
    if latest is None:
        return PeriodSelection(None, None, "No transactions")

    if period == "month":
        default_month = latest_available_month or latest
        try:
            start = (
                datetime.strptime(requested_month, "%Y-%m").date()
                if requested_month
                else default_month.replace(day=1)
            )
        except ValueError:
            start = default_month.replace(day=1)
        end = add_months(start, 1) - timedelta(days=1)
        return PeriodSelection(start, end, start.strftime("%B %Y"))

    if period == "year":
        start = date(latest.year, 1, 1)
        end = date(latest.year, 12, 31)
        return PeriodSelection(start, end, str(latest.year))

    start = earliest or latest
    return PeriodSelection(
        start,
        latest,
        f"{start.strftime('%b %Y')} – {latest.strftime('%b %Y')}",
    )
