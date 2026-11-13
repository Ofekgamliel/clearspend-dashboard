"""Pure coordination for long-period financial-observation analysis.

This module composes already-qualified historical rule families.  It owns no
SQLite, HTTP, or presentation behavior, and deliberately keeps reporting-month
transactions separate from purchase-date merchant activity.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping, Union

from clearspend.observations.historical_merchant_rules import (
    EstablishedMerchantHabitShift,
    HistoricalMerchantTransaction,
    RegularMerchantHabit,
    established_merchant_habit_shifts,
    newly_regular_merchant_habits,
)
from clearspend.observations.historical_rules import (
    AmountLeftTrend,
    CategoryRoutineShift,
    HistoricalCategoryTransaction,
    HistoricalHouseholdMonth,
    HistoricalInstallmentMonth,
    HistoricalRecurringMonth,
    HistoricalTransaction,
    PersistentInstallmentBurden,
    RecurringBurdenShift,
    SpendingRoutineShift,
    amount_left_trend,
    category_routine_shifts,
    persistent_installment_burden,
    recurring_burden_shift,
    routine_category_totals,
    routine_spending_totals,
    spending_routine_shift,
)


HistoricalObservationSignal = Union[
    AmountLeftTrend,
    SpendingRoutineShift,
    RecurringBurdenShift,
    PersistentInstallmentBurden,
    CategoryRoutineShift,
    RegularMerchantHabit,
    EstablishedMerchantHabitShift,
]


@dataclass(frozen=True)
class HistoricalObservationDataset:
    """Normalized inputs required by every long-period rule family."""

    target_months: tuple[str, ...]
    coverage_months: tuple[str, ...]
    routine_transactions: tuple[HistoricalTransaction, ...] = ()
    category_transactions: tuple[HistoricalCategoryTransaction, ...] = ()
    merchant_transactions: tuple[HistoricalMerchantTransaction, ...] = ()
    household_history: Mapping[str, HistoricalHouseholdMonth] = field(
        default_factory=dict,
    )
    recurring_history: Mapping[str, HistoricalRecurringMonth] = field(
        default_factory=dict,
    )
    installment_history: Mapping[str, HistoricalInstallmentMonth] = field(
        default_factory=dict,
    )
    recurring_aliases: tuple[str, ...] = ()
    partial_month: str = ""
    income_visible: bool = True


@dataclass(frozen=True)
class HistoricalObservationAnalysis:
    """Qualified historical findings in established card-priority order."""

    amount_left: AmountLeftTrend | None
    spending_routine: SpendingRoutineShift | None
    recurring_burden: RecurringBurdenShift | None
    installment_burden: PersistentInstallmentBurden | None
    category_routines: tuple[CategoryRoutineShift, ...]
    newly_regular_merchants: tuple[RegularMerchantHabit, ...]
    merchant_habit_shifts: tuple[EstablishedMerchantHabitShift, ...]

    @property
    def signals(self) -> tuple[HistoricalObservationSignal, ...]:
        """Flatten findings without losing the dashboard's type priority."""
        singletons = (
            self.amount_left,
            self.spending_routine,
            self.recurring_burden,
            self.installment_burden,
        )
        return (
            *(signal for signal in singletons if signal is not None),
            *self.category_routines,
            *self.newly_regular_merchants,
            *self.merchant_habit_shifts,
        )


def analyze_historical_observations(
    dataset: HistoricalObservationDataset,
) -> HistoricalObservationAnalysis:
    """Run every long-period rule once over one normalized input dataset."""
    partial_month = dataset.partial_month or None
    routine_totals = routine_spending_totals(
        dataset.coverage_months,
        dataset.routine_transactions,
    )
    category_totals = routine_category_totals(
        dataset.coverage_months,
        dataset.category_transactions,
    )
    return HistoricalObservationAnalysis(
        amount_left=amount_left_trend(
            dataset.target_months,
            dataset.coverage_months,
            dataset.household_history,
            partial_month=partial_month,
            income_visible=dataset.income_visible,
        ),
        spending_routine=spending_routine_shift(
            dataset.target_months,
            routine_totals,
            partial_month=partial_month,
        ),
        recurring_burden=recurring_burden_shift(
            dataset.target_months,
            dataset.coverage_months,
            dataset.recurring_history,
            partial_month=partial_month,
        ),
        installment_burden=persistent_installment_burden(
            dataset.target_months,
            dataset.installment_history,
            partial_month=partial_month,
        ),
        category_routines=category_routine_shifts(
            dataset.target_months,
            category_totals,
            dataset.category_transactions,
            partial_month=partial_month,
        ),
        newly_regular_merchants=newly_regular_merchant_habits(
            dataset.target_months,
            dataset.coverage_months,
            dataset.merchant_transactions,
            recurring_aliases=dataset.recurring_aliases,
            partial_month=partial_month,
        ),
        merchant_habit_shifts=established_merchant_habit_shifts(
            dataset.target_months,
            dataset.coverage_months,
            dataset.merchant_transactions,
            recurring_aliases=dataset.recurring_aliases,
            partial_month=partial_month,
        ),
    )
