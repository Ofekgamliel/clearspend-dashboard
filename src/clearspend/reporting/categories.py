from __future__ import annotations

from typing import Iterable, Mapping


def with_spending_shares(
    rows: Iterable[Mapping], total: float,
) -> list[dict]:
    """Return category rows with their percentage of the selected spending total."""
    result: list[dict] = []
    for source in rows:
        row = dict(source)
        row["share"] = round(float(row["amount"]) / total * 100, 1) if total else 0
        result.append(row)
    return result


def with_previous_month_comparison(
    rows: Iterable[Mapping],
    *,
    previous_transaction_count: int,
    previous_amounts: Mapping[str, float],
) -> list[dict]:
    """Add the established previous-month comparison fields to category rows."""
    result: list[dict] = []
    for source in rows:
        row = dict(source)
        previous_amount = round(previous_amounts.get(str(row["category"]), 0), 2)
        row["previous_amount"] = previous_amount
        if not previous_transaction_count:
            row["comparison"] = "unavailable"
            row["change_percent"] = None
        elif previous_amount <= 0:
            row["comparison"] = "new"
            row["change_percent"] = None
        else:
            change_percent = round(
                (float(row["amount"]) - previous_amount) / previous_amount * 100
            )
            row["change_percent"] = change_percent
            row["comparison"] = (
                "up" if change_percent > 0 else "down" if change_percent < 0 else "same"
            )
        result.append(row)
    return result
