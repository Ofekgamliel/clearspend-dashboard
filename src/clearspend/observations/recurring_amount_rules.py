"""Pure amount-change rules for reviewed recurring-payment observations.

This module qualifies findings only. It does not query recurring profiles,
verify statement coverage, format cards, or write review state. The production
browser engine remains authoritative until assembled observation parity is
proved.
"""

from __future__ import annotations

from dataclasses import dataclass
import re
from statistics import median
from typing import Iterable


FIXED_RECURRING = "Fixed recurring"
VARIABLE_RECURRING = "Usage-based recurring"
FIRST_FEE_OBSERVED = "FIRST FEE OBSERVED"
FEE_AMOUNT_INCREASED = "FEE AMOUNT INCREASED"
RECURRING_AMOUNT_INCREASED = "RECURRING AMOUNT INCREASED"
MAXIMUM_PRIOR_CHARGES = 6
FIXED_BASELINE_CHARGES = 3
DEFAULT_INCREASE_THRESHOLD = 1.0
JPY_INCREASE_THRESHOLD = 100.0

_FEE_PATTERN = re.compile(
    r"(?:^|\s)(?:fee|fees|commission|interest)(?:\s|$)"
    r"|עמל|דמי\s*(?:כרטיס|ניהול|טיפול)|ריבית",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class RecurringObservationCharge:
    id: int
    merchant_normalized: str
    provider: str
    card_last4: str
    transaction_date: str
    personal_amount: float
    charged_currency: str = "ILS"
    original_amount: float | None = None
    original_currency: str | None = None

    @property
    def stream_identity(self) -> tuple[str, str, str]:
        return (self.merchant_normalized, self.provider, self.card_last4)

    @property
    def is_foreign(self) -> bool:
        return bool(
            self.original_amount is not None
            and self.original_currency
            and self.original_currency
            not in {self.charged_currency, "₪", "ILS"}
        )


@dataclass(frozen=True)
class FirstFeeSignal:
    observation_type: str
    transaction_id: int
    observed_amount: float
    transaction_date: str
    coverage_confirmed: bool = False


@dataclass(frozen=True)
class RecurringAmountSignal:
    observation_type: str
    transaction_id: int
    recurring_type: str
    observed_amount: float
    comparison_currency: str
    baseline: float
    observed_minimum: float
    observed_maximum: float
    increase_above_comparison: float
    threshold: float
    comparison_charge_ids: tuple[int, ...]
    fixed: bool


def is_fee_description(value: str) -> bool:
    """Recognize the same fee wording used by the production observation UI."""
    return bool(_FEE_PATTERN.search(str(value or "")))


def _matching_prior_charges(
    current: RecurringObservationCharge,
    history: Iterable[RecurringObservationCharge],
) -> tuple[RecurringObservationCharge, ...]:
    matching = sorted(
        (
            charge
            for charge in history
            if charge.id != current.id
            and charge.stream_identity == current.stream_identity
            and charge.transaction_date < current.transaction_date
            and charge.personal_amount > 0
        ),
        key=lambda charge: charge.transaction_date,
    )
    return tuple(matching[-MAXIMUM_PRIOR_CHARGES:])


def recurring_charge_observation(
    current: RecurringObservationCharge,
    history: Iterable[RecurringObservationCharge],
    *,
    recurring_type: str,
    series_description: str,
) -> FirstFeeSignal | RecurringAmountSignal | None:
    """Qualify one reviewed recurring charge against its exact prior stream."""
    previous = _matching_prior_charges(current, history)
    fee_like = is_fee_description(series_description)
    if not previous:
        if not fee_like:
            return None
        return FirstFeeSignal(
            observation_type=FIRST_FEE_OBSERVED,
            transaction_id=current.id,
            observed_amount=current.personal_amount,
            transaction_date=current.transaction_date,
        )

    fixed = recurring_type == FIXED_RECURRING
    variable = recurring_type == VARIABLE_RECURRING
    if not fixed and not variable:
        return None

    comparison_rows = previous
    observed = current.personal_amount
    currency = "ILS"
    threshold = DEFAULT_INCREASE_THRESHOLD
    if current.is_foreign:
        currency = str(current.original_currency)
        comparison_rows = tuple(
            charge
            for charge in previous
            if charge.original_currency == currency
            and charge.original_amount is not None
        )
        if not comparison_rows:
            return None
        observed = float(current.original_amount)
        threshold = (
            JPY_INCREASE_THRESHOLD
            if currency.upper() == "JPY"
            else DEFAULT_INCREASE_THRESHOLD
        )

    if fixed:
        comparison_rows = comparison_rows[-FIXED_BASELINE_CHARGES:]
    amounts = tuple(
        float(charge.original_amount)
        if current.is_foreign
        else charge.personal_amount
        for charge in comparison_rows
    )
    baseline = float(median(amounts))
    observed_minimum = min(amounts)
    observed_maximum = max(amounts)
    comparison = baseline if fixed else observed_maximum
    increase = observed - comparison
    if increase < threshold:
        return None

    return RecurringAmountSignal(
        observation_type=(
            FEE_AMOUNT_INCREASED if fee_like else RECURRING_AMOUNT_INCREASED
        ),
        transaction_id=current.id,
        recurring_type=recurring_type,
        observed_amount=observed,
        comparison_currency=currency,
        baseline=baseline,
        observed_minimum=observed_minimum,
        observed_maximum=observed_maximum,
        increase_above_comparison=increase,
        threshold=threshold,
        comparison_charge_ids=tuple(charge.id for charge in comparison_rows),
        fixed=fixed,
    )
