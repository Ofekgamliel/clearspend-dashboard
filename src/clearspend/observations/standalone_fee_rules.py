"""Pure first-observed rules for fees outside reviewed recurring profiles."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from clearspend.observations.recurring_amount_rules import (
    FIRST_FEE_OBSERVED,
    is_fee_description,
)
from clearspend.reporting.periods import shift_month


FEE_LOOKBACK_MONTHS = 12


@dataclass(frozen=True)
class FeeObservationTransaction:
    id: int
    canonical_merchant_id: str
    merchant_normalized: str
    category: str
    month: str
    transaction_date: str
    personal_amount: float
    merchant_raw: str = ""
    merchant_display_name: str = ""
    notes: str = ""

    @property
    def identity(self) -> tuple[str, str]:
        return (
            self.canonical_merchant_id or self.merchant_normalized,
            self.category,
        )

    @property
    def fee_description(self) -> str:
        return f"{self.merchant_raw} {self.merchant_display_name} {self.notes}"


@dataclass(frozen=True)
class StandaloneFirstFeeSignal:
    observation_type: str
    transaction_id: int
    identity: tuple[str, str]
    observed_amount: float
    transaction_date: str
    history_start_month: str
    history_end_month: str
    coverage_confirmed: bool = False


def first_observed_standalone_fees(
    month: str,
    transactions: Iterable[FeeObservationTransaction],
    *,
    recurring_transaction_ids: Iterable[int] = (),
) -> tuple[StandaloneFirstFeeSignal, ...]:
    """Find fee-like current charges absent from the prior 12-month lookback.

    A result means only that no matching fee was found in imported data. It is
    never promoted to a confirmed new fee without separate coverage evidence.
    """
    rows = tuple(transactions)
    recurring_ids = {int(value) for value in recurring_transaction_ids}
    history_start = shift_month(month, -FEE_LOOKBACK_MONTHS)
    history_end = shift_month(month, -1)
    signals: list[StandaloneFirstFeeSignal] = []
    for current in rows:
        if (
            current.month != month
            or current.personal_amount <= 0
            or current.id in recurring_ids
            or not is_fee_description(current.fee_description)
        ):
            continue
        has_prior_fee = any(
            candidate.id != current.id
            and candidate.identity == current.identity
            and history_start <= candidate.month < month
            and is_fee_description(candidate.fee_description)
            for candidate in rows
        )
        if has_prior_fee:
            continue
        signals.append(StandaloneFirstFeeSignal(
            observation_type=FIRST_FEE_OBSERVED,
            transaction_id=current.id,
            identity=current.identity,
            observed_amount=current.personal_amount,
            transaction_date=current.transaction_date,
            history_start_month=history_start,
            history_end_month=history_end,
        ))
    return tuple(signals)
