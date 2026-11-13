"""Coordinate pure single-month financial-observation rules.

This module owns qualification order and cross-rule suppression only. It does
not query SQLite, construct cards, apply review state, or expose an HTTP API.
The browser observation engine remains authoritative until assembled payload
parity is proved.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping, Union

from clearspend.observations.monthly_rules import (
    AmountLeftSignal,
    CategorySpendingSignal,
    HouseholdMonth,
    MerchantActivityMonth,
    MerchantActivitySignal,
    amount_left_decrease,
    category_spending_increase,
    merchant_activity_change,
)
from clearspend.observations.recurring_amount_rules import (
    FirstFeeSignal,
    RecurringAmountSignal,
    RecurringObservationCharge,
    recurring_charge_observation,
)
from clearspend.observations.recurring_cycle_rules import (
    AdditionalRecurringChargeSignal,
    additional_recurring_charges,
)
from clearspend.observations.standalone_fee_rules import (
    FeeObservationTransaction,
    StandaloneFirstFeeSignal,
    first_observed_standalone_fees,
)
from clearspend.observations.transaction_rules import (
    DuplicateCandidate,
    ObservationTransaction,
    PurchaseSignal,
    possible_duplicate_groups,
    purchase_signal,
)
from clearspend.reporting.periods import shift_month


@dataclass(frozen=True)
class MonthlyObservationTransaction:
    id: int
    report_month: str
    merchant_raw: str
    merchant_normalized: str
    merchant_display_name: str
    canonical_merchant_id: str
    category: str
    provider: str
    card_last4: str
    transaction_date: str
    charged_amount: float
    charged_currency: str
    personal_amount: float
    installment_total: int | None = None
    original_amount: float | None = None
    original_currency: str | None = None
    notes: str = ""
    event_id: int | str | None = None
    event_name: str = ""

    @property
    def identity(self) -> tuple[str, str]:
        return (
            self.canonical_merchant_id or self.merchant_normalized,
            self.category,
        )

    @property
    def label(self) -> str:
        return self.merchant_display_name or self.merchant_raw or "Unknown merchant"

    def as_observation_transaction(self) -> ObservationTransaction:
        return ObservationTransaction(
            id=self.id,
            merchant_normalized=self.merchant_normalized,
            canonical_merchant_id=self.canonical_merchant_id,
            category=self.category,
            provider=self.provider,
            card_last4=self.card_last4,
            transaction_date=self.transaction_date,
            month=self.report_month,
            charged_amount=self.charged_amount,
            charged_currency=self.charged_currency,
            personal_amount=self.personal_amount,
            installment_total=self.installment_total,
        )

    def as_recurring_charge(self) -> RecurringObservationCharge:
        return RecurringObservationCharge(
            id=self.id,
            merchant_normalized=self.merchant_normalized,
            provider=self.provider,
            card_last4=self.card_last4,
            transaction_date=self.transaction_date,
            personal_amount=self.personal_amount,
            charged_currency=self.charged_currency,
            original_amount=self.original_amount,
            original_currency=self.original_currency,
        )

    def as_fee_transaction(self) -> FeeObservationTransaction:
        return FeeObservationTransaction(
            id=self.id,
            canonical_merchant_id=self.canonical_merchant_id,
            merchant_normalized=self.merchant_normalized,
            category=self.category,
            month=self.report_month,
            transaction_date=self.transaction_date,
            personal_amount=self.personal_amount,
            merchant_raw=self.merchant_raw,
            merchant_display_name=self.merchant_display_name,
            notes=self.notes,
        )


@dataclass(frozen=True)
class MonthlyRecurringSeries:
    series_id: str
    display_name: str
    category: str
    recurring_type: str
    cadence: str
    source_aliases: tuple[str, ...] = ()

    def matches(self, transaction: MonthlyObservationTransaction) -> bool:
        return (
            transaction.merchant_raw in self.source_aliases
            and transaction.category == self.category
        )


@dataclass(frozen=True)
class MonthlyDuplicateFinding:
    label: str
    signal: DuplicateCandidate


RecurringSignal = Union[
    FirstFeeSignal,
    RecurringAmountSignal,
    AdditionalRecurringChargeSignal,
]


@dataclass(frozen=True)
class MonthlyRecurringFinding:
    label: str
    series_id: str
    signal: RecurringSignal


@dataclass(frozen=True)
class MonthlyMerchantActivityFinding:
    identity: tuple[str, str]
    label: str
    signal: MerchantActivitySignal


@dataclass(frozen=True)
class MonthlyPurchaseFinding:
    label: str
    signal: PurchaseSignal


@dataclass(frozen=True)
class MonthlyStandaloneFeeFinding:
    label: str
    signal: StandaloneFirstFeeSignal


@dataclass(frozen=True)
class MonthlyObservationDataset:
    month: str
    coverage_months: tuple[str, ...]
    transactions: tuple[MonthlyObservationTransaction, ...] = ()
    recurring_series: tuple[MonthlyRecurringSeries, ...] = ()
    household_history: Mapping[str, HouseholdMonth] = field(default_factory=dict)
    partial_month: str = ""
    income_visible: bool = False


@dataclass(frozen=True)
class MonthlyObservationAnalysis:
    amount_left: AmountLeftSignal | None = None
    category_spending: tuple[CategorySpendingSignal, ...] = ()
    possible_duplicates: tuple[MonthlyDuplicateFinding, ...] = ()
    recurring_findings: tuple[MonthlyRecurringFinding, ...] = ()
    merchant_activity: tuple[MonthlyMerchantActivityFinding, ...] = ()
    purchases: tuple[MonthlyPurchaseFinding, ...] = ()
    standalone_fees: tuple[MonthlyStandaloneFeeFinding, ...] = ()
    duplicate_transaction_ids: frozenset[int] = frozenset()
    recurring_transaction_ids: frozenset[int] = frozenset()

    @property
    def signals(self) -> tuple[object, ...]:
        """Return raw findings in the established monthly family order."""
        values: list[object] = []
        if self.amount_left is not None:
            values.append(self.amount_left)
        values.extend(self.category_spending)
        values.extend(self.possible_duplicates)
        values.extend(self.recurring_findings)
        values.extend(self.merchant_activity)
        values.extend(self.purchases)
        values.extend(self.standalone_fees)
        return tuple(values)


def _previous_three(month: str) -> tuple[str, str, str]:
    return tuple(shift_month(month, offset) for offset in (-1, -2, -3))


def _routine_category_totals(
    transactions: tuple[MonthlyObservationTransaction, ...],
) -> tuple[dict[str, dict[str, float]], dict[str, float]]:
    categories: dict[str, dict[str, float]] = {}
    totals: dict[str, float] = {}
    for transaction in transactions:
        if transaction.personal_amount <= 0 or transaction.event_id is not None:
            continue
        month_values = categories.setdefault(transaction.report_month, {})
        month_values[transaction.category] = (
            month_values.get(transaction.category, 0.0)
            + transaction.personal_amount
        )
        totals[transaction.report_month] = (
            totals.get(transaction.report_month, 0.0)
            + transaction.personal_amount
        )
    return categories, totals


def analyze_monthly_observations(
    dataset: MonthlyObservationDataset,
) -> MonthlyObservationAnalysis:
    """Apply single-month rules with browser-equivalent exclusions.

    Reporting month drives month comparisons. Reviewed recurring profiles use
    exact statement alias plus category. Event purchases remain in total
    personal spending but are excluded from routine-category and merchant
    activity comparisons.
    """
    month = dataset.month
    covered = frozenset(dataset.coverage_months)
    rows = tuple(
        transaction
        for transaction in dataset.transactions
        if transaction.report_month in covered
    )
    current = tuple(
        transaction
        for transaction in rows
        if transaction.report_month == month and transaction.personal_amount > 0
    )
    observation_rows = tuple(row.as_observation_transaction() for row in rows)
    current_observation_rows = tuple(
        row.as_observation_transaction() for row in current
    )
    previous = _previous_three(month)

    amount_left = None
    if dataset.income_visible and month != dataset.partial_month:
        current_household = dataset.household_history.get(month)
        prior_household = tuple(
            dataset.household_history.get(value) for value in previous
        )
        if current_household is not None and all(prior_household):
            amount_left = amount_left_decrease(
                current_household,
                tuple(value for value in prior_household if value is not None),
            )

    category_findings: list[CategorySpendingSignal] = []
    if month != dataset.partial_month:
        category_history, routine_totals = _routine_category_totals(rows)
        for category, current_amount in sorted(
            category_history.get(month, {}).items(),
        ):
            signal = category_spending_increase(
                category,
                current_amount,
                routine_totals.get(month, 0.0),
                tuple(
                    category_history.get(value, {}).get(category, 0.0)
                    for value in previous
                ),
            )
            if signal is not None:
                category_findings.append(signal)

    duplicates = possible_duplicate_groups(current_observation_rows)
    duplicate_ids = frozenset(
        transaction_id
        for signal in duplicates
        for transaction_id in signal.transaction_ids
    )
    current_by_id = {transaction.id: transaction for transaction in current}
    duplicate_findings = tuple(
        MonthlyDuplicateFinding(
            label=current_by_id[signal.transaction_ids[0]].label,
            signal=signal,
        )
        for signal in duplicates
    )

    recurring_ids: set[int] = set()
    recurring_findings: list[MonthlyRecurringFinding] = []
    for series in dataset.recurring_series:
        profile = tuple(
            transaction
            for transaction in rows
            if transaction.personal_amount > 0 and series.matches(transaction)
        )
        current_profile = tuple(
            transaction for transaction in profile if transaction.report_month == month
        )
        recurring_ids.update(transaction.id for transaction in current_profile)
        recurring_charges = tuple(
            transaction.as_recurring_charge() for transaction in profile
        )
        for transaction in current_profile:
            signal = recurring_charge_observation(
                transaction.as_recurring_charge(),
                recurring_charges,
                recurring_type=series.recurring_type,
                series_description=(
                    f"{series.display_name} {' '.join(series.source_aliases)}"
                ),
            )
            if signal is not None:
                recurring_findings.append(MonthlyRecurringFinding(
                    label=series.display_name or transaction.label,
                    series_id=series.series_id,
                    signal=signal,
                ))
        if series.cadence == "Monthly":
            for signal in additional_recurring_charges(
                series.series_id,
                month,
                recurring_charges,
                duplicate_transaction_ids=duplicate_ids,
            ):
                recurring_ids.update(signal.transaction_ids)
                first = next(
                    transaction
                    for transaction in profile
                    if transaction.id == signal.transaction_ids[0]
                )
                recurring_findings.append(MonthlyRecurringFinding(
                    label=first.label,
                    series_id=series.series_id,
                    signal=signal,
                ))

    activity_findings: list[MonthlyMerchantActivityFinding] = []
    changed_identities: set[tuple[str, str]] = set()
    current_activity: dict[
        tuple[str, str], list[MonthlyObservationTransaction]
    ] = {}
    for transaction in current:
        if transaction.event_id is None and transaction.id not in recurring_ids:
            current_activity.setdefault(transaction.identity, []).append(transaction)
    for identity, activity_rows in current_activity.items():
        history: list[MerchantActivityMonth] = []
        for history_month in previous:
            matching = tuple(
                transaction
                for transaction in rows
                if transaction.report_month == history_month
                and transaction.identity == identity
                and transaction.personal_amount > 0
                and transaction.event_id is None
                and transaction.id not in recurring_ids
            )
            history.append(MerchantActivityMonth(
                history_month,
                len(matching),
                sum(transaction.personal_amount for transaction in matching),
            ))
        signal = merchant_activity_change(
            MerchantActivityMonth(
                month,
                len(activity_rows),
                sum(transaction.personal_amount for transaction in activity_rows),
            ),
            history,
        )
        if signal is not None:
            changed_identities.add(identity)
            activity_findings.append(MonthlyMerchantActivityFinding(
                identity=identity,
                label=activity_rows[0].label,
                signal=signal,
            ))

    monthly_total = sum(transaction.personal_amount for transaction in current)
    purchase_findings: list[MonthlyPurchaseFinding] = []
    for transaction in current:
        if transaction.id in recurring_ids or transaction.id in duplicate_ids:
            continue
        signal = purchase_signal(
            transaction.as_observation_transaction(),
            observation_rows,
            monthly_positive_personal_spending=monthly_total,
            merchant_activity_already_changed=(
                transaction.identity in changed_identities
            ),
        )
        if signal is not None:
            purchase_findings.append(MonthlyPurchaseFinding(
                label=transaction.label,
                signal=signal,
            ))

    fee_signals = first_observed_standalone_fees(
        month,
        tuple(transaction.as_fee_transaction() for transaction in rows),
        recurring_transaction_ids=recurring_ids,
    )
    row_by_id = {transaction.id: transaction for transaction in rows}
    standalone_fees = tuple(
        MonthlyStandaloneFeeFinding(
            label=row_by_id[signal.transaction_id].label,
            signal=signal,
        )
        for signal in fee_signals
    )

    return MonthlyObservationAnalysis(
        amount_left=amount_left,
        category_spending=tuple(category_findings),
        possible_duplicates=duplicate_findings,
        recurring_findings=tuple(recurring_findings),
        merchant_activity=tuple(activity_findings),
        purchases=tuple(purchase_findings),
        standalone_fees=standalone_fees,
        duplicate_transaction_ids=duplicate_ids,
        recurring_transaction_ids=frozenset(recurring_ids),
    )
