"""Pure shared mechanics and spending rules for long-period observations."""

from __future__ import annotations

from dataclasses import dataclass
from statistics import median
from typing import Callable, Iterable, Mapping


SPENDING_ROUTINE_SHIFTED = "SPENDING ROUTINE SHIFTED"
AMOUNT_LEFT_TREND = "AMOUNT LEFT TREND"
CATEGORY_ROUTINE_SHIFTED = "CATEGORY ROUTINE SHIFTED"
RECURRING_BURDEN_SHIFTED = "RECURRING BURDEN SHIFTED"
PERSISTENT_INSTALLMENT_BURDEN = "PERSISTENT INSTALLMENT BURDEN"
POST_CHANGE_MONTHS = 3
MAXIMUM_BASELINE_MONTHS = 6
MINIMUM_BASELINE_MONTHS = 3
SPENDING_CHANGE_RATIO = 0.20
SPENDING_CHANGE_AMOUNT = 1_000.0
INCOME_GROWTH_MINIMUM = 0.10
INCOME_GROWTH_GAP_MINIMUM = 0.10
AMOUNT_LEFT_CHANGE_MINIMUM = 1_500.0
AMOUNT_LEFT_PERCENTAGE_POINT_MINIMUM = 10.0
CATEGORY_INCREASE_RATIO = 1.50
CATEGORY_DECREASE_RATIO = 0.60
CATEGORY_CHANGE_AMOUNT = 500.0
RECURRING_COUNT_CHANGE_MINIMUM = 2.0
RECURRING_COST_CHANGE_MINIMUM = 100.0
RECURRING_COST_INCREASE_RATIO = 1.15
RECURRING_COST_DECREASE_RATIO = 0.85
INSTALLMENT_WINDOW_MONTHS = 6
INSTALLMENT_MONTHLY_MINIMUM = 500.0
INSTALLMENT_AVERAGE_MINIMUM = 1_000.0

_CADENCE_DIVISORS = {
    "Weekly": 0.25,
    "Monthly": 1.0,
    "Every 2 months": 2.0,
    "Quarterly": 3.0,
    "Every 6 months": 6.0,
    "Yearly": 12.0,
}
_INACTIVE_RECURRING_STATUSES = {"ended", "paused", "completed"}


@dataclass(frozen=True)
class HistoricalTransaction:
    month: str
    personal_amount: float
    event_id: int | None = None


@dataclass(frozen=True)
class HistoricalHouseholdMonth:
    month: str
    income: float
    spending: float

    @property
    def amount_left(self) -> float:
        return self.income - self.spending

    @property
    def percentage_left(self) -> float:
        return self.amount_left / self.income * 100 if self.income > 0 else 0.0


@dataclass(frozen=True)
class HistoricalCategoryTransaction:
    month: str
    category: str | None
    merchant_label: str
    personal_amount: float
    event_id: int | None = None


@dataclass(frozen=True)
class HistoricalRecurringSeries:
    series_id: str
    amount: float
    cadence: str
    status: str
    display_name: str = ""
    source_aliases: tuple[str, ...] = ()

    @property
    def monthly_equivalent(self) -> float:
        return float(self.amount) / _CADENCE_DIVISORS.get(self.cadence, 1.0)

    @property
    def label(self) -> str:
        if self.display_name:
            return self.display_name
        if self.source_aliases:
            return self.source_aliases[0]
        return "Unnamed service"


@dataclass(frozen=True)
class HistoricalRecurringMonth:
    month: str
    series: tuple[HistoricalRecurringSeries, ...]
    active_series_count: int | None = None


@dataclass(frozen=True)
class HistoricalInstallmentPlan:
    plan_id: str | None = None
    source_alias: str = ""
    display_name: str = ""
    original_purchase_date: str = ""
    original_amount: float | str = ""
    installment_total: int | str = ""

    @property
    def identity(self) -> str:
        if self.plan_id:
            return self.plan_id
        return "|".join(str(value) for value in (
            self.source_alias or self.display_name,
            self.original_purchase_date,
            self.original_amount,
            self.installment_total,
        ))


@dataclass(frozen=True)
class HistoricalInstallmentMonth:
    month: str
    installment_billed: float
    commitments: tuple[HistoricalInstallmentPlan, ...] = ()


@dataclass(frozen=True)
class ChangeWindow:
    start: str
    index: int
    pre_months: tuple[str, ...]
    post_months: tuple[str, ...]


@dataclass(frozen=True)
class PatternLifecycle:
    duration: int
    active: bool


@dataclass(frozen=True)
class SpendingRoutineShift:
    observation_type: str
    start_month: str
    pre_months: tuple[str, ...]
    post_months: tuple[str, ...]
    pre_values: tuple[float, ...]
    post_values: tuple[float, ...]
    baseline: float
    post_average: float
    direction: int
    duration: int
    active: bool
    score: float
    difference: float
    change_percentage: float

    @property
    def higher(self) -> bool:
        return self.direction > 0


@dataclass(frozen=True)
class AmountLeftTrend:
    observation_type: str
    kind: str
    start_month: str
    pre_months: tuple[str, ...]
    post_months: tuple[str, ...]
    pre_rows: tuple[HistoricalHouseholdMonth, ...]
    post_rows: tuple[HistoricalHouseholdMonth, ...]
    duration: int
    active: bool
    severity: int
    score: float
    overspent_months: int = 0
    average_shortfall: float | None = None
    baseline_income: float | None = None
    post_income: float | None = None
    baseline_spending: float | None = None
    post_spending: float | None = None
    income_growth: float | None = None
    spending_growth: float | None = None
    growth_gap: float | None = None
    baseline_left: float | None = None
    post_left: float | None = None
    baseline_percentage: float | None = None
    post_percentage: float | None = None
    amount_change: float | None = None
    percentage_point_change: float | None = None


@dataclass(frozen=True)
class CategoryRoutineShift:
    observation_type: str
    category: str
    start_month: str
    pre_months: tuple[str, ...]
    post_months: tuple[str, ...]
    pre_values: tuple[float, ...]
    post_values: tuple[float, ...]
    baseline: float
    post_average: float
    direction: int
    duration: int
    active: bool
    score: float
    drivers: tuple[str, ...]

    @property
    def higher(self) -> bool:
        return self.direction > 0


@dataclass(frozen=True)
class RecurringSeriesAmountChange:
    name: str
    before: float
    after: float


@dataclass(frozen=True)
class RecurringBurdenShift:
    observation_type: str
    start_month: str
    pre_months: tuple[str, ...]
    post_months: tuple[str, ...]
    count_baseline: float
    count_after: float
    cost_baseline: float
    cost_after: float
    count_shift: bool
    cost_shift: bool
    duration: int
    active: bool
    score: float
    started: tuple[str, ...]
    ended: tuple[str, ...]
    changed: tuple[RecurringSeriesAmountChange, ...]


@dataclass(frozen=True)
class PersistentInstallmentBurden:
    observation_type: str
    start_month: str
    months: tuple[str, ...]
    burdens: tuple[float, ...]
    duration: int
    active: bool
    average_burden: float
    starts: int
    endings: int
    replacements: bool
    score: float


@dataclass(frozen=True)
class _SpendingCandidate:
    window: ChangeWindow
    lifecycle: PatternLifecycle
    pre_values: tuple[float, ...]
    post_values: tuple[float, ...]
    baseline: float
    post_average: float
    direction: int
    score: float


@dataclass(frozen=True)
class _CategoryCandidate:
    window: ChangeWindow
    lifecycle: PatternLifecycle
    pre_values: tuple[float, ...]
    post_values: tuple[float, ...]
    baseline: float
    post_average: float
    direction: int
    score: float


def routine_spending_totals(
    covered_months: Iterable[str],
    transactions: Iterable[HistoricalTransaction],
) -> dict[str, float]:
    """Aggregate positive personal spending outside projects and events."""
    totals = {month: 0.0 for month in covered_months}
    for transaction in transactions:
        if transaction.month not in totals or transaction.event_id:
            continue
        totals[transaction.month] += max(0.0, float(transaction.personal_amount))
    return totals


def routine_category_totals(
    covered_months: Iterable[str],
    transactions: Iterable[HistoricalCategoryTransaction],
) -> dict[str, dict[str, float]]:
    """Aggregate positive category spending outside projects and events."""
    totals: dict[str, dict[str, float]] = {month: {} for month in covered_months}
    for transaction in transactions:
        if transaction.month not in totals or transaction.event_id:
            continue
        amount = max(0.0, float(transaction.personal_amount))
        if amount <= 0:
            continue
        category = transaction.category or "Needs review"
        month_totals = totals[transaction.month]
        month_totals[category] = month_totals.get(category, 0.0) + amount
    return totals


def candidate_change_windows(
    selected_months: Iterable[str],
    history_months: Iterable[str],
) -> tuple[ChangeWindow, ...]:
    """Build the established three-month post and six-month pre windows."""
    selected = tuple(selected_months)
    history = tuple(sorted(history_months))
    windows: list[ChangeWindow] = []
    for index, start in enumerate(selected[:-2]):
        pre = tuple(month for month in history if month < start)[-MAXIMUM_BASELINE_MONTHS:]
        if len(pre) < MINIMUM_BASELINE_MONTHS:
            continue
        windows.append(ChangeWindow(
            start=start,
            index=index,
            pre_months=pre,
            post_months=selected[index:index + POST_CHANGE_MONTHS],
        ))
    return tuple(windows)


def pattern_lifecycle(
    selected_months: Iterable[str],
    window: ChangeWindow,
    is_on_new_side: Callable[[str], bool],
) -> PatternLifecycle:
    """Measure consecutive duration and whether the latest two months agree."""
    selected = tuple(selected_months)
    duration = 0
    for month in selected[window.index:]:
        if not is_on_new_side(month):
            break
        duration += 1
    tail = selected[-2:]
    return PatternLifecycle(
        duration=max(POST_CHANGE_MONTHS, duration),
        active=len(tail) == 2 and all(is_on_new_side(month) for month in tail),
    )


def spending_routine_shift(
    target_months: Iterable[str],
    monthly_routine_spending: Mapping[str, float],
    *,
    partial_month: str | None = None,
) -> SpendingRoutineShift | None:
    """Find the strongest lasting shift in routine monthly spending."""
    selected = tuple(month for month in target_months if month != partial_month)
    history = tuple(
        sorted(month for month in monthly_routine_spending if month != partial_month)
    )
    if len(selected) < POST_CHANGE_MONTHS:
        return None

    def amount(month: str) -> float:
        return float(monthly_routine_spending.get(month, 0.0))

    candidates: list[_SpendingCandidate] = []
    for window in candidate_change_windows(selected, history):
        pre_values = tuple(amount(month) for month in window.pre_months)
        post_values = tuple(amount(month) for month in window.post_months)
        baseline = float(median(pre_values))
        if baseline <= 0:
            continue
        recent_median = float(median(post_values))
        direction = 1 if recent_median > baseline else -1

        def crosses(value: float) -> bool:
            if direction > 0:
                return (
                    value >= baseline * (1 + SPENDING_CHANGE_RATIO)
                    and value - baseline >= SPENDING_CHANGE_AMOUNT
                )
            return (
                value <= baseline * (1 - SPENDING_CHANGE_RATIO)
                and baseline - value >= SPENDING_CHANGE_AMOUNT
            )

        def same_side_value(value: float) -> bool:
            return value > baseline if direction > 0 else value < baseline

        if (
            sum(crosses(value) for value in post_values) < 2
            or not all(same_side_value(value) for value in post_values)
        ):
            continue
        lifecycle = pattern_lifecycle(
            selected, window, lambda month: same_side_value(amount(month)),
        )
        candidates.append(_SpendingCandidate(
            window=window,
            lifecycle=lifecycle,
            pre_values=pre_values,
            post_values=post_values,
            baseline=baseline,
            post_average=sum(post_values) / len(post_values),
            direction=direction,
            score=abs(recent_median - baseline),
        ))

    if not candidates:
        return None
    best = min(
        candidates,
        key=lambda candidate: (
            -candidate.lifecycle.duration,
            -candidate.score,
            candidate.window.start,
        ),
    )
    difference = best.post_average - best.baseline
    return SpendingRoutineShift(
        observation_type=SPENDING_ROUTINE_SHIFTED,
        start_month=best.window.start,
        pre_months=best.window.pre_months,
        post_months=best.window.post_months,
        pre_values=best.pre_values,
        post_values=best.post_values,
        baseline=best.baseline,
        post_average=best.post_average,
        direction=best.direction,
        duration=best.lifecycle.duration,
        active=best.lifecycle.active,
        score=best.score,
        difference=difference,
        change_percentage=difference / best.baseline * 100,
    )


def amount_left_trend(
    target_months: Iterable[str],
    coverage_months: Iterable[str],
    household_history: Mapping[str, HistoricalHouseholdMonth],
    *,
    partial_month: str | None = None,
    income_visible: bool = True,
) -> AmountLeftTrend | None:
    """Find the highest-severity lasting income-versus-spending pattern."""
    if not income_visible:
        return None
    selected = tuple(month for month in target_months if month != partial_month)
    coverage = tuple(month for month in coverage_months if month != partial_month)
    if len(selected) < POST_CHANGE_MONTHS:
        return None
    candidates: list[AmountLeftTrend] = []

    for window in candidate_change_windows(selected, coverage):
        pre_rows = tuple(
            household_history[month]
            for month in window.pre_months
            if month in household_history and household_history[month].income > 0
        )
        post_rows_raw = tuple(household_history.get(month) for month in window.post_months)
        if (
            len(pre_rows) < MINIMUM_BASELINE_MONTHS
            or any(row is None or row.income <= 0 for row in post_rows_raw)
        ):
            continue
        post_rows = tuple(row for row in post_rows_raw if row is not None)
        overspent = tuple(row for row in post_rows if row.amount_left < 0)

        if len(overspent) >= 2:
            average_shortfall = sum(abs(row.amount_left) for row in overspent) / len(overspent)
            lifecycle = pattern_lifecycle(
                selected,
                window,
                lambda month: (
                    month in household_history
                    and household_history[month].income > 0
                    and household_history[month].spending > household_history[month].income
                ),
            )
            candidates.append(AmountLeftTrend(
                observation_type=AMOUNT_LEFT_TREND,
                kind="repeated_overspending",
                start_month=window.start,
                pre_months=window.pre_months,
                post_months=window.post_months,
                pre_rows=pre_rows,
                post_rows=post_rows,
                duration=lifecycle.duration,
                active=lifecycle.active,
                severity=3,
                score=average_shortfall,
                overspent_months=len(overspent),
                average_shortfall=average_shortfall,
            ))
            continue

        baseline_income = float(median(row.income for row in pre_rows))
        post_income = sum(row.income for row in post_rows) / len(post_rows)
        baseline_spending = float(median(row.spending for row in pre_rows))
        post_spending = sum(row.spending for row in post_rows) / len(post_rows)
        if baseline_income > 0 and baseline_spending > 0:
            income_growth = post_income / baseline_income - 1
            spending_growth = post_spending / baseline_spending - 1
            growth_gap = spending_growth - income_growth
            if (
                spending_growth >= INCOME_GROWTH_MINIMUM
                and growth_gap >= INCOME_GROWTH_GAP_MINIMUM
            ):
                lifecycle = pattern_lifecycle(
                    selected,
                    window,
                    lambda month: (
                        month in household_history
                        and household_history[month].income > 0
                        and household_history[month].spending / baseline_spending
                        > household_history[month].income / baseline_income
                    ),
                )
                candidates.append(AmountLeftTrend(
                    observation_type=AMOUNT_LEFT_TREND,
                    kind="spending_outgrew_income",
                    start_month=window.start,
                    pre_months=window.pre_months,
                    post_months=window.post_months,
                    pre_rows=pre_rows,
                    post_rows=post_rows,
                    duration=lifecycle.duration,
                    active=lifecycle.active,
                    severity=2,
                    score=growth_gap * 10_000,
                    baseline_income=baseline_income,
                    post_income=post_income,
                    baseline_spending=baseline_spending,
                    post_spending=post_spending,
                    income_growth=income_growth,
                    spending_growth=spending_growth,
                    growth_gap=growth_gap,
                ))
                continue

        baseline_left = float(median(row.amount_left for row in pre_rows))
        post_left = sum(row.amount_left for row in post_rows) / len(post_rows)
        baseline_percentage = float(median(row.percentage_left for row in pre_rows))
        post_percentage = sum(row.percentage_left for row in post_rows) / len(post_rows)
        amount_change = post_left - baseline_left
        percentage_change = post_percentage - baseline_percentage
        same_direction = (
            amount_change != 0
            and percentage_change != 0
            and (amount_change > 0) == (percentage_change > 0)
        )
        if (
            not same_direction
            or abs(amount_change) < AMOUNT_LEFT_CHANGE_MINIMUM
            or abs(percentage_change) < AMOUNT_LEFT_PERCENTAGE_POINT_MINIMUM
        ):
            continue
        direction = 1 if amount_change > 0 else -1

        def remains_shifted(month: str) -> bool:
            row = household_history.get(month)
            if row is None or row.income <= 0:
                return False
            if direction > 0:
                return (
                    row.amount_left > baseline_left
                    and row.percentage_left > baseline_percentage
                )
            return (
                row.amount_left < baseline_left
                and row.percentage_left < baseline_percentage
            )

        lifecycle = pattern_lifecycle(selected, window, remains_shifted)
        candidates.append(AmountLeftTrend(
            observation_type=AMOUNT_LEFT_TREND,
            kind="amount_left_shift",
            start_month=window.start,
            pre_months=window.pre_months,
            post_months=window.post_months,
            pre_rows=pre_rows,
            post_rows=post_rows,
            duration=lifecycle.duration,
            active=lifecycle.active,
            severity=1,
            score=abs(amount_change),
            baseline_left=baseline_left,
            post_left=post_left,
            baseline_percentage=baseline_percentage,
            post_percentage=post_percentage,
            amount_change=amount_change,
            percentage_point_change=percentage_change,
        ))

    if not candidates:
        return None
    return min(
        candidates,
        key=lambda candidate: (
            -candidate.severity,
            -candidate.duration,
            -candidate.score,
            candidate.start_month,
        ),
    )


def category_routine_shifts(
    target_months: Iterable[str],
    monthly_category_spending: Mapping[str, Mapping[str, float]],
    transactions: Iterable[HistoricalCategoryTransaction] = (),
    *,
    partial_month: str | None = None,
) -> tuple[CategoryRoutineShift, ...]:
    """Find lasting routine-spending shifts independently for each category."""
    selected = tuple(month for month in target_months if month != partial_month)
    history = tuple(
        sorted(month for month in monthly_category_spending if month != partial_month)
    )
    if len(selected) < POST_CHANGE_MONTHS:
        return ()

    category_names: list[str] = []
    seen_categories: set[str] = set()
    for month in history:
        for category in monthly_category_spending.get(month, {}):
            if category not in seen_categories:
                seen_categories.add(category)
                category_names.append(category)

    transaction_rows = tuple(transactions)
    findings: list[CategoryRoutineShift] = []
    for category in category_names:
        def amount(month: str) -> float:
            return float(monthly_category_spending.get(month, {}).get(category, 0.0))

        candidates: list[_CategoryCandidate] = []
        for window in candidate_change_windows(selected, history):
            pre_values = tuple(amount(month) for month in window.pre_months)
            post_values = tuple(amount(month) for month in window.post_months)
            if sum(value > 0 for value in pre_values) < MINIMUM_BASELINE_MONTHS:
                continue
            baseline = float(median(pre_values))
            if baseline <= 0:
                continue
            post_median = float(median(post_values))
            direction = 1 if post_median > baseline else -1

            def crosses(value: float) -> bool:
                if direction > 0:
                    return (
                        value >= baseline * CATEGORY_INCREASE_RATIO
                        and value - baseline >= CATEGORY_CHANGE_AMOUNT
                    )
                return (
                    value <= baseline * CATEGORY_DECREASE_RATIO
                    and baseline - value >= CATEGORY_CHANGE_AMOUNT
                )

            def same_side_value(value: float) -> bool:
                return value > baseline if direction > 0 else value < baseline

            if direction > 0 and sum(value > 0 for value in post_values) < 2:
                continue
            if (
                sum(crosses(value) for value in post_values) < 2
                or not all(same_side_value(value) for value in post_values)
            ):
                continue
            lifecycle = pattern_lifecycle(
                selected, window, lambda month: same_side_value(amount(month)),
            )
            candidates.append(_CategoryCandidate(
                window=window,
                lifecycle=lifecycle,
                pre_values=pre_values,
                post_values=post_values,
                baseline=baseline,
                post_average=sum(post_values) / len(post_values),
                direction=direction,
                score=abs(post_median - baseline),
            ))

        if not candidates:
            continue
        best = min(
            candidates,
            key=lambda candidate: (
                -candidate.lifecycle.duration,
                -candidate.score,
                candidate.window.start,
            ),
        )
        contributor_amounts: dict[str, float] = {}
        compared_months = {*best.window.pre_months, *best.window.post_months}
        for transaction in transaction_rows:
            transaction_category = transaction.category or "Needs review"
            amount_value = float(transaction.personal_amount)
            if (
                transaction.month not in compared_months
                or transaction.event_id
                or transaction_category != category
                or amount_value <= 0
            ):
                continue
            contributor_amounts[transaction.merchant_label] = (
                contributor_amounts.get(transaction.merchant_label, 0.0)
                + amount_value
            )
        drivers = tuple(
            name
            for name, _amount in sorted(
                contributor_amounts.items(), key=lambda item: -item[1],
            )[:3]
        )
        findings.append(CategoryRoutineShift(
            observation_type=CATEGORY_ROUTINE_SHIFTED,
            category=category,
            start_month=best.window.start,
            pre_months=best.window.pre_months,
            post_months=best.window.post_months,
            pre_values=best.pre_values,
            post_values=best.post_values,
            baseline=best.baseline,
            post_average=best.post_average,
            direction=best.direction,
            duration=best.lifecycle.duration,
            active=best.lifecycle.active,
            score=best.score,
            drivers=drivers,
        ))
    return tuple(findings)


def recurring_burden_shift(
    target_months: Iterable[str],
    coverage_months: Iterable[str],
    recurring_history: Mapping[str, HistoricalRecurringMonth],
    *,
    partial_month: str | None = None,
) -> RecurringBurdenShift | None:
    """Find a lasting shift in normalized recurring cost or service count."""
    selected = tuple(month for month in target_months if month != partial_month)
    coverage = tuple(month for month in coverage_months if month != partial_month)
    if len(selected) < POST_CHANGE_MONTHS:
        return None

    def active_series(month: str) -> tuple[HistoricalRecurringSeries, ...]:
        snapshot = recurring_history.get(month)
        if snapshot is None:
            return ()
        return tuple(
            series
            for series in snapshot.series
            if series.status not in _INACTIVE_RECURRING_STATUSES
        )

    def service_count(month: str) -> float:
        snapshot = recurring_history.get(month)
        if snapshot is None:
            return 0.0
        if snapshot.active_series_count is not None:
            return float(snapshot.active_series_count)
        return float(len(active_series(month)))

    def monthly_equivalent(month: str) -> float:
        return sum(series.monthly_equivalent for series in active_series(month))

    candidates: list[RecurringBurdenShift] = []
    for window in candidate_change_windows(selected, coverage):
        pre_counts = tuple(service_count(month) for month in window.pre_months)
        post_counts = tuple(service_count(month) for month in window.post_months)
        pre_costs = tuple(monthly_equivalent(month) for month in window.pre_months)
        post_costs = tuple(monthly_equivalent(month) for month in window.post_months)
        count_baseline = float(median(pre_counts))
        count_after = sum(post_counts) / len(post_counts)
        cost_baseline = float(median(pre_costs))
        cost_after = sum(post_costs) / len(post_costs)
        count_change = count_after - count_baseline
        cost_change = cost_after - cost_baseline
        count_shift = (
            abs(count_change) >= RECURRING_COUNT_CHANGE_MINIMUM
            and sum(
                value >= count_baseline + 1
                if count_change > 0
                else value <= count_baseline - 1
                for value in post_counts
            ) >= 2
        )
        cost_shift = (
            cost_baseline > 0
            and abs(cost_change) >= RECURRING_COST_CHANGE_MINIMUM
            and (
                cost_after / cost_baseline >= RECURRING_COST_INCREASE_RATIO
                or cost_after / cost_baseline <= RECURRING_COST_DECREASE_RATIO
            )
        )
        if not count_shift and not cost_shift:
            continue
        direction = (
            1 if cost_change > 0 else -1
        ) if cost_shift else (1 if count_change > 0 else -1)

        def remains_shifted(month: str) -> bool:
            count = service_count(month)
            cost = monthly_equivalent(month)
            if direction > 0:
                return (
                    (count > count_baseline if count_shift else True)
                    and (cost > cost_baseline if cost_shift else True)
                )
            return (
                (count < count_baseline if count_shift else True)
                and (cost < cost_baseline if cost_shift else True)
            )

        lifecycle = pattern_lifecycle(selected, window, remains_shifted)
        before = {
            series.series_id: series for series in active_series(window.pre_months[-1])
        }
        after = {
            series.series_id: series for series in active_series(window.post_months[-1])
        }
        started = tuple(
            after[series_id].label for series_id in after if series_id not in before
        )
        ended = tuple(
            before[series_id].label for series_id in before if series_id not in after
        )
        changed = tuple(
            RecurringSeriesAmountChange(
                name=after[series_id].label,
                before=before[series_id].monthly_equivalent,
                after=after[series_id].monthly_equivalent,
            )
            for series_id in after
            if (
                series_id in before
                and abs(
                    after[series_id].monthly_equivalent
                    - before[series_id].monthly_equivalent
                ) >= 1
            )
        )
        candidates.append(RecurringBurdenShift(
            observation_type=RECURRING_BURDEN_SHIFTED,
            start_month=window.start,
            pre_months=window.pre_months,
            post_months=window.post_months,
            count_baseline=count_baseline,
            count_after=count_after,
            cost_baseline=cost_baseline,
            cost_after=cost_after,
            count_shift=count_shift,
            cost_shift=cost_shift,
            duration=lifecycle.duration,
            active=lifecycle.active,
            score=abs(cost_change) + abs(count_change) * 250,
            started=started,
            ended=ended,
            changed=changed,
        ))

    if not candidates:
        return None
    return min(
        candidates,
        key=lambda candidate: (
            -candidate.duration,
            -candidate.score,
            candidate.start_month,
        ),
    )


def persistent_installment_burden(
    target_months: Iterable[str],
    installment_history: Mapping[str, HistoricalInstallmentMonth],
    *,
    partial_month: str | None = None,
) -> PersistentInstallmentBurden | None:
    """Find six or more consecutive months with a material installment load."""
    selected = tuple(month for month in target_months if month != partial_month)
    if len(selected) < INSTALLMENT_WINDOW_MONTHS:
        return None

    def burden(month: str) -> float:
        snapshot = installment_history.get(month)
        return float(snapshot.installment_billed) if snapshot else 0.0

    def plans(month: str) -> set[str]:
        snapshot = installment_history.get(month)
        if snapshot is None:
            return set()
        return {plan.identity for plan in snapshot.commitments}

    candidates: list[PersistentInstallmentBurden] = []
    for index in range(len(selected) - INSTALLMENT_WINDOW_MONTHS + 1):
        months = selected[index:index + INSTALLMENT_WINDOW_MONTHS]
        burdens = tuple(burden(month) for month in months)
        average_burden = sum(burdens) / len(burdens)
        if (
            min(burdens) < INSTALLMENT_MONTHLY_MINIMUM
            or average_burden < INSTALLMENT_AVERAGE_MINIMUM
        ):
            continue
        plan_sets = tuple(plans(month) for month in months)
        starts = 0
        endings = 0
        for previous, current in zip(plan_sets, plan_sets[1:]):
            starts += len(current - previous)
            endings += len(previous - current)
        duration = INSTALLMENT_WINDOW_MONTHS
        for month in selected[index + INSTALLMENT_WINDOW_MONTHS:]:
            if burden(month) < INSTALLMENT_MONTHLY_MINIMUM:
                break
            duration += 1
        replacements = starts >= 2 and endings >= 2
        candidates.append(PersistentInstallmentBurden(
            observation_type=PERSISTENT_INSTALLMENT_BURDEN,
            start_month=months[0],
            months=months,
            burdens=burdens,
            duration=duration,
            active=index + duration == len(selected),
            average_burden=average_burden,
            starts=starts,
            endings=endings,
            replacements=replacements,
            score=average_burden * duration,
        ))

    if not candidates:
        return None
    return min(
        candidates,
        key=lambda candidate: (
            -candidate.duration,
            -candidate.score,
            candidate.start_month,
        ),
    )
