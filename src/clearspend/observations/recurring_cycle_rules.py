"""Pure billing-cycle rules for additional recurring-charge observations."""

from __future__ import annotations

from calendar import monthrange
from dataclasses import dataclass
from datetime import date
from math import floor
from statistics import median
from typing import Iterable
from urllib.parse import quote

from clearspend.observations.recurring_amount_rules import RecurringObservationCharge


ADDITIONAL_RECURRING_CHARGE = "ADDITIONAL RECURRING CHARGE"
MINIMUM_LEARNING_CHARGES = 3
MAXIMUM_LEARNING_CHARGES = 6
OCCURRENCE_WINDOW_DAYS = 7


@dataclass(frozen=True)
class AdditionalRecurringChargeSignal:
    observation_type: str
    recurring_series_id: str
    expected_date: str
    transaction_ids: tuple[int, ...]
    occurrence_start: str
    occurrence_end: str
    charge_count: int
    additional_count: int
    total_amount: float
    learned_days: tuple[int, ...]
    finding_key: str


def recurring_review_key(
    series_id: str,
    expected_date: str,
    transaction_ids: Iterable[int],
) -> str:
    encoded_series = quote(str(series_id), safe="-_.!~*'()")
    ids = sorted({int(value) for value in transaction_ids})
    return (
        f"{ADDITIONAL_RECURRING_CHARGE}:{encoded_series}:{expected_date}:"
        f"{','.join(str(value) for value in ids)}"
    )


def _parsed_date(value: str) -> date | None:
    try:
        return date.fromisoformat(value)
    except (TypeError, ValueError):
        return None


def _expected_date(month: str, day: int) -> date:
    year, month_number = (int(value) for value in month.split("-", 1))
    return date(year, month_number, min(day, monthrange(year, month_number)[1]))


def additional_recurring_charges(
    series_id: str,
    month: str,
    charges: Iterable[RecurringObservationCharge],
    *,
    duplicate_transaction_ids: Iterable[int] = (),
) -> tuple[AdditionalRecurringChargeSignal, ...]:
    """Find multiple charges near one learned monthly occurrence.

    Charges are grouped by exact alias, provider, and card. The caller supplies
    only charges belonging to one reviewed recurring profile and invokes this
    rule only for monthly cadence.
    """
    duplicate_ids = {int(value) for value in duplicate_transaction_ids}
    grouped: dict[tuple[str, str, str], list[RecurringObservationCharge]] = {}
    for charge in charges:
        if charge.personal_amount <= 0 or _parsed_date(charge.transaction_date) is None:
            continue
        grouped.setdefault(charge.stream_identity, []).append(charge)

    month_start = f"{month}-01"
    signals: list[AdditionalRecurringChargeSignal] = []
    for stream in grouped.values():
        stream.sort(key=lambda charge: charge.transaction_date)
        earlier = [
            charge
            for charge in stream
            if charge.transaction_date < month_start
        ]
        if len(earlier) < MINIMUM_LEARNING_CHARGES:
            continue
        learned_days = tuple(
            int(charge.transaction_date[8:10])
            for charge in earlier[-MAXIMUM_LEARNING_CHARGES:]
        )
        # JavaScript Math.round rounds positive halves upward; Python's round
        # uses bankers' rounding, so preserve the production behavior directly.
        expected = _expected_date(month, floor(float(median(learned_days)) + 0.5))
        occurrence = [
            charge
            for charge in stream
            if abs((_parsed_date(charge.transaction_date) - expected).days)
            <= OCCURRENCE_WINDOW_DAYS
        ]
        if (
            len(occurrence) <= 1
            or all(charge.id in duplicate_ids for charge in occurrence)
        ):
            continue

        transaction_ids = tuple(charge.id for charge in occurrence)
        dates = tuple(charge.transaction_date for charge in occurrence)
        expected_text = expected.isoformat()
        signals.append(AdditionalRecurringChargeSignal(
            observation_type=ADDITIONAL_RECURRING_CHARGE,
            recurring_series_id=str(series_id),
            expected_date=expected_text,
            transaction_ids=transaction_ids,
            occurrence_start=min(dates),
            occurrence_end=max(dates),
            charge_count=len(occurrence),
            additional_count=len(occurrence) - 1,
            total_amount=sum(charge.personal_amount for charge in occurrence),
            learned_days=learned_days,
            finding_key=recurring_review_key(
                str(series_id), expected_text, transaction_ids,
            ),
        ))
    return tuple(sorted(signals, key=lambda signal: signal.transaction_ids))
