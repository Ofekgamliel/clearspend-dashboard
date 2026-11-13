"""Pure monthly qualification rules for financial observations.

The functions in this module mirror the established browser calculations but
do not query SQLite or construct presentation text. They are intentionally not
wired into the HTTP API yet; the browser observation engine remains
authoritative until assembled-payload parity is proved.
"""

from __future__ import annotations

from dataclasses import dataclass
from statistics import median
from typing import Iterable


AMOUNT_LEFT_OBSERVATION = "AMOUNT LEFT DECREASED"
CATEGORY_SPENDING_OBSERVATION = "CATEGORY SPENDING INCREASED"
MERCHANT_ACTIVITY_OBSERVATION = "MERCHANT ACTIVITY CHANGED"
AMOUNT_LEFT_MINIMUM_DROP = 2_000.0
AMOUNT_LEFT_MINIMUM_PERCENTAGE_POINT_DROP = 15.0
CATEGORY_MINIMUM_RATIO = 2.0
CATEGORY_MINIMUM_INCREASE = 1_000.0
CATEGORY_MINIMUM_ROUTINE_SHARE = 0.075
MERCHANT_SPENDING_MINIMUM_RATIO = 1.75
MERCHANT_SPENDING_MINIMUM_INCREASE = 200.0
MERCHANT_COUNT_MINIMUM_RATIO = 2.0
MERCHANT_COUNT_MINIMUM_INCREASE = 3.0
MERCHANT_MINIMUM_ACTIVE_HISTORY_MONTHS = 2
MERCHANT_MINIMUM_HISTORY_PURCHASES = 5
COMPARISON_MONTHS = 3


@dataclass(frozen=True)
class HouseholdMonth:
    month: str
    income: float
    spending: float

    @property
    def remaining(self) -> float:
        return self.income - self.spending

    @property
    def remaining_percentage(self) -> float:
        return self.remaining / self.income * 100 if self.income > 0 else 0.0


@dataclass(frozen=True)
class AmountLeftSignal:
    month: str
    observation_type: str
    income: float
    spending: float
    remaining: float
    remaining_percentage: float
    baseline_remaining: float
    baseline_percentage: float
    amount_drop: float
    percentage_point_drop: float
    overspent: bool
    comparison_months: tuple[str, ...]


@dataclass(frozen=True)
class CategorySpendingSignal:
    category: str
    observation_type: str
    current_amount: float
    routine_total: float
    previous_amounts: tuple[float, ...]
    active_history_months: int
    baseline: float
    increase: float
    ratio: float
    routine_share: float


@dataclass(frozen=True)
class MerchantActivityMonth:
    month: str
    purchase_count: int
    total: float


@dataclass(frozen=True)
class MerchantActivitySignal:
    observation_type: str
    current_month: str
    current_count: int
    current_total: float
    active_history: tuple[MerchantActivityMonth, ...]
    history_purchase_count: int
    baseline_count: float
    baseline_total: float
    spending_changed: bool
    purchase_count_changed: bool
    spending_ratio: float
    purchase_count_ratio: float


def amount_left_decrease(
    current: HouseholdMonth,
    previous: Iterable[HouseholdMonth],
) -> AmountLeftSignal | None:
    """Return a signal when materially less income remains this month.

    The comparison requires exactly three prior months with income. Exceeding
    income always qualifies; otherwise both the shekel and percentage-point
    decline thresholds must be met.
    """
    history = tuple(previous)
    if (
        current.income <= 0
        or len(history) != COMPARISON_MONTHS
        or any(month.income <= 0 for month in history)
    ):
        return None

    baseline_remaining = float(median(month.remaining for month in history))
    baseline_percentage = float(
        median(month.remaining_percentage for month in history)
    )
    amount_drop = baseline_remaining - current.remaining
    percentage_drop = baseline_percentage - current.remaining_percentage
    overspent = current.remaining < 0
    if not overspent and not (
        amount_drop >= AMOUNT_LEFT_MINIMUM_DROP
        and percentage_drop >= AMOUNT_LEFT_MINIMUM_PERCENTAGE_POINT_DROP
    ):
        return None

    return AmountLeftSignal(
        month=current.month,
        observation_type=AMOUNT_LEFT_OBSERVATION,
        income=current.income,
        spending=current.spending,
        remaining=current.remaining,
        remaining_percentage=current.remaining_percentage,
        baseline_remaining=baseline_remaining,
        baseline_percentage=baseline_percentage,
        amount_drop=amount_drop,
        percentage_point_drop=percentage_drop,
        overspent=overspent,
        comparison_months=tuple(month.month for month in history),
    )


def category_spending_increase(
    category: str,
    current_amount: float,
    routine_total: float,
    previous_amounts: Iterable[float],
) -> CategorySpendingSignal | None:
    """Return a signal for a material sustained routine-category increase.

    Missing category spending in an otherwise covered month is represented by
    zero and remains part of the three-month median, matching the dashboard.
    """
    history = tuple(float(amount) for amount in previous_amounts)
    current = float(current_amount)
    total = float(routine_total)
    if (
        len(history) != COMPARISON_MONTHS
        or sum(amount > 0 for amount in history) < 2
        or total <= 0
    ):
        return None

    baseline = float(median(history))
    if baseline <= 0:
        return None
    increase = current - baseline
    ratio = current / baseline
    share = current / total
    if (
        ratio < CATEGORY_MINIMUM_RATIO
        or increase < CATEGORY_MINIMUM_INCREASE
        or share < CATEGORY_MINIMUM_ROUTINE_SHARE
    ):
        return None

    return CategorySpendingSignal(
        category=category,
        observation_type=CATEGORY_SPENDING_OBSERVATION,
        current_amount=current,
        routine_total=total,
        previous_amounts=history,
        active_history_months=sum(amount > 0 for amount in history),
        baseline=baseline,
        increase=increase,
        ratio=ratio,
        routine_share=share,
    )


def merchant_activity_change(
    current: MerchantActivityMonth,
    previous: Iterable[MerchantActivityMonth],
) -> MerchantActivitySignal | None:
    """Return a signal when routine non-recurring merchant activity increases.

    Callers aggregate one merchant-and-category identity after excluding event
    purchases and reviewed recurring charges. Zero-count covered months remain
    comparison slots but do not enter the active-month medians.
    """
    history = tuple(previous)
    if (
        len(history) != COMPARISON_MONTHS
        or current.purchase_count <= 0
        or current.total <= 0
    ):
        return None
    active = tuple(month for month in history if month.purchase_count > 0)
    history_count = sum(month.purchase_count for month in active)
    if (
        len(active) < MERCHANT_MINIMUM_ACTIVE_HISTORY_MONTHS
        or history_count < MERCHANT_MINIMUM_HISTORY_PURCHASES
    ):
        return None

    baseline_total = float(median(month.total for month in active))
    baseline_count = float(median(month.purchase_count for month in active))
    if baseline_total <= 0 or baseline_count <= 0:
        return None
    spending_ratio = current.total / baseline_total
    count_ratio = current.purchase_count / baseline_count
    spending_changed = bool(
        spending_ratio >= MERCHANT_SPENDING_MINIMUM_RATIO
        and current.total - baseline_total >= MERCHANT_SPENDING_MINIMUM_INCREASE
    )
    count_changed = bool(
        count_ratio >= MERCHANT_COUNT_MINIMUM_RATIO
        and current.purchase_count - baseline_count >= MERCHANT_COUNT_MINIMUM_INCREASE
    )
    if not spending_changed and not count_changed:
        return None

    return MerchantActivitySignal(
        observation_type=MERCHANT_ACTIVITY_OBSERVATION,
        current_month=current.month,
        current_count=current.purchase_count,
        current_total=current.total,
        active_history=active,
        history_purchase_count=history_count,
        baseline_count=baseline_count,
        baseline_total=baseline_total,
        spending_changed=spending_changed,
        purchase_count_changed=count_changed,
        spending_ratio=spending_ratio,
        purchase_count_ratio=count_ratio,
    )
