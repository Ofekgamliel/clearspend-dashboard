"""Pure merchant-habit rules for long-period financial observations."""

from __future__ import annotations

from dataclasses import dataclass
from statistics import median
from typing import Iterable

from clearspend.observations.historical_rules import (
    ChangeWindow,
    PatternLifecycle,
    candidate_change_windows,
    pattern_lifecycle,
)


MERCHANT_HABIT_SHIFTED = "MERCHANT HABIT SHIFTED"
MONEY_TRANSFER_CATEGORY = "העברת כספים"
MAXIMUM_BASELINE_MONTHS = 6
MINIMUM_BASELINE_MONTHS = 3
REGULAR_SPENDING_MINIMUM = 200.0


@dataclass(frozen=True)
class HistoricalMerchantTransaction:
    identity: str
    merchant_label: str
    merchant_raw: str
    transaction_date: str
    personal_amount: float
    category: str = ""
    installment_total: int | None = None
    event_id: int | str | None = None

    @property
    def purchase_month(self) -> str:
        return self.transaction_date[:7]


@dataclass(frozen=True)
class RegularMerchantHabit:
    observation_type: str
    identity: str
    merchant_label: str
    start_month: str
    pre_months: tuple[str, ...]
    establishment_months: tuple[str, ...]
    purchase_count: int
    purchase_days: int
    monthly_spending: tuple[float, ...]
    average_monthly_spending: float
    established_frequency: float
    prior_active_months: int
    later_months: int
    later_active_months: int
    recent_frequency: float
    spending_qualified: bool
    frequency_qualified: bool
    buying_more: bool
    still_visible: bool
    score: float
    establishment_purchase_counts: tuple[int, ...] = ()
    recent_months: tuple[str, ...] = ()
    recent_purchase_counts: tuple[int, ...] = ()
    recent_spending: tuple[float, ...] = ()


@dataclass(frozen=True)
class EstablishedMerchantHabitShift:
    observation_type: str
    identity: str
    merchant_label: str
    kind: str
    start_month: str
    pre_months: tuple[str, ...]
    post_months: tuple[str, ...]
    pre_count: float
    post_count: float
    pre_typical_amount: float
    post_typical_amount: float
    post_counts: tuple[int, ...]
    post_spending: tuple[float, ...]
    duration: int
    active: bool
    score: float


@dataclass(frozen=True)
class _EstablishedCandidate:
    window: ChangeWindow
    lifecycle: PatternLifecycle
    kind: str
    pre_count: float
    post_count: float
    pre_typical: float
    post_typical: float
    post_counts: tuple[int, ...]
    post_spending: tuple[float, ...]
    score: float


def _eligible_purchase_history(
    history: tuple[str, ...],
    transactions: Iterable[HistoricalMerchantTransaction],
    recurring_aliases: Iterable[str],
) -> dict[str, list[HistoricalMerchantTransaction]]:
    recurring = set(recurring_aliases)
    purchase_history: dict[str, list[HistoricalMerchantTransaction]] = {
        month: [] for month in history
    }
    for transaction in transactions:
        if (
            transaction.event_id
            or transaction.merchant_raw in recurring
            or int(transaction.installment_total or 0) > 1
            or transaction.category == MONEY_TRANSFER_CATEGORY
            or float(transaction.personal_amount) <= 0
            or transaction.purchase_month not in purchase_history
        ):
            continue
        purchase_history[transaction.purchase_month].append(transaction)
    return purchase_history


def _merchant_identities(
    history: tuple[str, ...],
    purchase_history: dict[str, list[HistoricalMerchantTransaction]],
) -> dict[str, str]:
    identities: dict[str, str] = {}
    for month in history:
        for transaction in purchase_history[month]:
            identities.setdefault(transaction.identity, transaction.merchant_label)
    return identities


def newly_regular_merchant_habits(
    target_months: Iterable[str],
    coverage_months: Iterable[str],
    transactions: Iterable[HistoricalMerchantTransaction],
    *,
    recurring_aliases: Iterable[str] = (),
    partial_month: str | None = None,
) -> tuple[RegularMerchantHabit, ...]:
    """Find merchants that establish repeated non-recurring purchase activity."""
    selected = tuple(month for month in target_months if month != partial_month)
    history = tuple(sorted(month for month in coverage_months if month != partial_month))
    transaction_rows = tuple(transactions)
    purchase_history = _eligible_purchase_history(
        history, transaction_rows, recurring_aliases,
    )
    identities = _merchant_identities(history, purchase_history)

    findings: list[RegularMerchantHabit] = []
    for identity, label in identities.items():
        def rows_for(month: str) -> tuple[HistoricalMerchantTransaction, ...]:
            return tuple(
                transaction
                for transaction in purchase_history.get(month, ())
                if transaction.identity == identity
            )

        for index, start in enumerate(selected):
            pre = tuple(month for month in history if month < start)[
                -MAXIMUM_BASELINE_MONTHS:
            ]
            prior_active = sum(bool(rows_for(month)) for month in pre)
            if len(pre) < MINIMUM_BASELINE_MONTHS or prior_active > 1:
                continue
            next_three = selected[index:index + 3]
            next_six = selected[index:index + 6]
            direct_consecutive = (
                len(next_three) == 3 and all(rows_for(month) for month in next_three)
            )
            consecutive_index: int | None = 0 if direct_consecutive else None
            if consecutive_index is None:
                for position in range(min(4, len(next_six))):
                    candidate = next_six[position:position + 3]
                    if len(candidate) == 3 and all(rows_for(month) for month in candidate):
                        consecutive_index = position
                        break
            consecutive = consecutive_index is not None
            four_of_six = (
                len(next_six) == 6
                and sum(bool(rows_for(month)) for month in next_six) >= 4
            )
            if consecutive:
                window = next_six[consecutive_index:consecutive_index + 3]
            elif four_of_six:
                window = next_six
            else:
                continue
            window_rows = tuple(
                transaction for month in window for transaction in rows_for(month)
            )
            purchase_days = len({
                transaction.transaction_date
                for transaction in window_rows
                if transaction.transaction_date
            })
            monthly_spending = tuple(
                sum(float(transaction.personal_amount) for transaction in rows_for(month))
                for month in window
            )
            average_spending = sum(monthly_spending) / len(monthly_spending)
            spending_qualified = average_spending >= REGULAR_SPENDING_MINIMUM
            frequency_qualified = (
                len(window_rows) >= 6 and purchase_days >= 4
                if consecutive
                else len(window_rows) >= 8 and purchase_days >= 6
            )
            if not spending_qualified and not frequency_qualified:
                continue
            actual_start = next(month for month in window if rows_for(month))
            following = tuple(month for month in selected if month >= actual_start)
            later = tuple(month for month in following if month > window[-1])
            later_active = sum(bool(rows_for(month)) for month in later)
            recent = following[-3:]
            recent_rows = tuple(
                transaction for month in recent for transaction in rows_for(month)
            )
            recent_frequency = len(recent_rows) / len(recent) if recent else 0.0
            established_frequency = len(window_rows) / len(window)
            buying_more = (
                sum(bool(rows_for(month)) for month in recent) >= 2
                and recent_frequency >= established_frequency * 1.75
                and recent_frequency - established_frequency >= 2
            )
            still_visible = sum(bool(rows_for(month)) for month in recent) >= 2
            findings.append(RegularMerchantHabit(
                observation_type=MERCHANT_HABIT_SHIFTED,
                identity=identity,
                merchant_label=label,
                start_month=actual_start,
                pre_months=pre,
                establishment_months=window,
                purchase_count=len(window_rows),
                purchase_days=purchase_days,
                monthly_spending=monthly_spending,
                average_monthly_spending=average_spending,
                established_frequency=established_frequency,
                prior_active_months=prior_active,
                later_months=len(later),
                later_active_months=later_active,
                recent_frequency=recent_frequency,
                spending_qualified=spending_qualified,
                frequency_qualified=frequency_qualified,
                buying_more=buying_more,
                still_visible=still_visible,
                score=len(window_rows) * 100 + average_spending,
                establishment_purchase_counts=tuple(
                    len(rows_for(month)) for month in window
                ),
                recent_months=recent,
                recent_purchase_counts=tuple(
                    len(rows_for(month)) for month in recent
                ),
                recent_spending=tuple(
                    sum(
                        float(transaction.personal_amount)
                        for transaction in rows_for(month)
                    )
                    for month in recent
                ),
            ))
            break
    return tuple(findings)


def established_merchant_habit_shifts(
    target_months: Iterable[str],
    coverage_months: Iterable[str],
    transactions: Iterable[HistoricalMerchantTransaction],
    *,
    recurring_aliases: Iterable[str] = (),
    partial_month: str | None = None,
) -> tuple[EstablishedMerchantHabitShift, ...]:
    """Find sustained frequency or typical-amount changes for known merchants."""
    selected = tuple(month for month in target_months if month != partial_month)
    history = tuple(sorted(month for month in coverage_months if month != partial_month))
    transaction_rows = tuple(transactions)
    recurring = tuple(recurring_aliases)
    purchase_history = _eligible_purchase_history(history, transaction_rows, recurring)
    identities = _merchant_identities(history, purchase_history)
    regular_identities = {
        finding.identity
        for finding in newly_regular_merchant_habits(
            selected,
            history,
            transaction_rows,
            recurring_aliases=recurring,
        )
    }
    findings: list[EstablishedMerchantHabitShift] = []

    for identity, label in identities.items():
        if identity in regular_identities:
            continue

        def rows_for(month: str) -> tuple[HistoricalMerchantTransaction, ...]:
            return tuple(
                transaction
                for transaction in purchase_history.get(month, ())
                if transaction.identity == identity
            )

        candidates: list[_EstablishedCandidate] = []
        for window in candidate_change_windows(selected, history):
            pre_rows = tuple(
                transaction
                for month in window.pre_months
                for transaction in rows_for(month)
            )
            post_by_month = tuple(rows_for(month) for month in window.post_months)
            post_rows = tuple(
                transaction for rows in post_by_month for transaction in rows
            )
            pre_active = tuple(
                month for month in window.pre_months if rows_for(month)
            )
            if len(pre_active) < 3 or sum(bool(rows) for rows in post_by_month) < 2:
                continue
            pre_counts = tuple(len(rows_for(month)) for month in pre_active)
            post_counts = tuple(len(rows) for rows in post_by_month)
            pre_typical = float(median(
                float(transaction.personal_amount) for transaction in pre_rows
            ))
            post_typical = float(median(
                float(transaction.personal_amount) for transaction in post_rows
            ))
            pre_count = float(median(pre_counts))
            post_count = sum(post_counts) / len(post_counts)
            frequency_ratio = post_count / pre_count if pre_count else 0.0
            price_ratio = post_typical / pre_typical if pre_typical else 0.0
            buying_more = (
                frequency_ratio >= 1.75
                and post_count - pre_count >= 2
                and 0.8 <= price_ratio <= 1.2
            )
            buying_less = (
                frequency_ratio <= 0.6
                and pre_count - post_count >= 2
                and 0.8 <= price_ratio <= 1.2
            )
            price_up = (
                price_ratio >= 1.2
                and post_typical - pre_typical >= 20
                and 0.75 <= frequency_ratio <= 1.25
            )
            price_down = (
                price_ratio <= 0.8
                and pre_typical - post_typical >= 20
                and 0.75 <= frequency_ratio <= 1.25
            )
            if not any((buying_more, buying_less, price_up, price_down)):
                continue
            if buying_more:
                kind = "Buying more often"
                direction = 1
            elif buying_less:
                kind = "Buying less often"
                direction = -1
            elif price_up:
                kind = "Typical purchase amount increased"
                direction = 1
            else:
                kind = "Typical purchase amount decreased"
                direction = -1
            frequency_kind = buying_more or buying_less

            def remains_shifted(month: str) -> bool:
                rows = rows_for(month)
                if frequency_kind:
                    return len(rows) > pre_count if direction > 0 else len(rows) < pre_count
                typical = float(median(
                    [float(transaction.personal_amount) for transaction in rows]
                )) if rows else 0.0
                return typical > pre_typical if direction > 0 else typical < pre_typical

            lifecycle = pattern_lifecycle(selected, window, remains_shifted)
            score = (
                abs(post_count - pre_count) * 100
                if frequency_kind
                else abs(post_typical - pre_typical)
            )
            candidates.append(_EstablishedCandidate(
                window=window,
                lifecycle=lifecycle,
                kind=kind,
                pre_count=pre_count,
                post_count=post_count,
                pre_typical=pre_typical,
                post_typical=post_typical,
                post_counts=post_counts,
                post_spending=tuple(
                    sum(float(transaction.personal_amount) for transaction in rows)
                    for rows in post_by_month
                ),
                score=score,
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
        findings.append(EstablishedMerchantHabitShift(
            observation_type=MERCHANT_HABIT_SHIFTED,
            identity=identity,
            merchant_label=label,
            kind=best.kind,
            start_month=best.window.start,
            pre_months=best.window.pre_months,
            post_months=best.window.post_months,
            pre_count=best.pre_count,
            post_count=best.post_count,
            pre_typical_amount=best.pre_typical,
            post_typical_amount=best.post_typical,
            post_counts=best.post_counts,
            post_spending=best.post_spending,
            duration=best.lifecycle.duration,
            active=best.lifecycle.active,
            score=best.score,
        ))
    return tuple(findings)
