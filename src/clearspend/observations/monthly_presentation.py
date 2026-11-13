"""Presentation mapping for qualified single-month observation signals."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP

from clearspend.observations.grouping import (
    ObservationFinding,
    ObservationGroup,
    assemble_active_observation_groups,
)
from clearspend.observations.monthly_analysis import (
    MonthlyDuplicateFinding,
    MonthlyMerchantActivityFinding,
    MonthlyObservationAnalysis,
    MonthlyObservationDataset,
    MonthlyObservationTransaction,
    MonthlyPurchaseFinding,
    MonthlyRecurringFinding,
    MonthlyStandaloneFeeFinding,
)
from clearspend.observations.recurring_amount_rules import (
    FirstFeeSignal,
    RecurringAmountSignal,
)
from clearspend.observations.recurring_cycle_rules import (
    AdditionalRecurringChargeSignal,
)


def _money(value: float) -> str:
    rounded = Decimal(str(float(value))).quantize(
        Decimal("0.01"), rounding=ROUND_HALF_UP,
    )
    return f"₪{rounded:,.2f}"


def _currency_money(value: float, currency: str) -> str:
    rounded = Decimal(str(float(value))).quantize(
        Decimal("0.01"), rounding=ROUND_HALF_UP,
    )
    return f"{currency} {rounded:,.2f}".strip()


def _month(value: str) -> str:
    try:
        label = datetime.strptime(value, "%Y-%m").strftime("%b %Y")
        return label.replace("Sep ", "Sept ")
    except (TypeError, ValueError):
        return str(value or "")


def _range(months: tuple[str, ...]) -> str:
    values = tuple(sorted(dict.fromkeys(month for month in months if month)))
    if not values:
        return ""
    return _month(values[0]) if len(values) == 1 else f"{_month(values[0])} – {_month(values[-1])}"


def _events(transactions: tuple[MonthlyObservationTransaction, ...]) -> str:
    return " · ".join(dict.fromkeys(
        transaction.event_name for transaction in transactions if transaction.event_name
    ))


def _transaction_index(
    dataset: MonthlyObservationDataset,
) -> dict[int, MonthlyObservationTransaction]:
    return {transaction.id: transaction for transaction in dataset.transactions}


def _fee_history(dataset: MonthlyObservationDataset) -> tuple[str, str]:
    start = _shift_month(dataset.month, -12)
    end = _shift_month(dataset.month, -1)
    imported = tuple(
        month for month in dataset.coverage_months if start <= month < dataset.month
    )
    history = _range(imported) if imported else "No earlier imported history"
    detail = (
        f"Searched the selected card scope from {_month(start)} through {_month(end)}. "
        "Imported history is present, but complete statement coverage has not been verified."
    )
    return history, detail


def _shift_month(value: str, offset: int) -> str:
    year, month = (int(part) for part in value.split("-", 1))
    number = year * 12 + month - 1 + offset
    return f"{number // 12:04d}-{number % 12 + 1:02d}"


def _amount_left_finding(
    analysis: MonthlyObservationAnalysis,
    dataset: MonthlyObservationDataset,
) -> ObservationFinding | None:
    signal = analysis.amount_left
    if signal is None:
        return None
    return ObservationFinding(
        observation_type=signal.observation_type,
        month=signal.month,
        label="All-card household",
        entity_label=_month(signal.month),
        entity_sublabel="All cards and purchase types",
        title=f"Less income remained in {_month(signal.month)}",
        description=(
            "After every included card purchase and reimbursement adjustment, "
            f"{signal.remaining_percentage:.1f}% of income remained versus a "
            f"{signal.baseline_percentage:.1f}% recent median."
        ),
        value=f"{_money(signal.remaining)} · {signal.remaining_percentage:.1f}% left",
        comparison=(
            f"{_money(signal.baseline_remaining)} · "
            f"{signal.baseline_percentage:.1f}% left"
        ),
        comparison_detail=(
            "Median of the previous three complete months · "
            f"{_range(signal.comparison_months)}"
        ),
        result=(
            f"{_money(abs(signal.remaining))} over income"
            if signal.overspent else
            f"{signal.percentage_point_drop:.1f} percentage points less left"
        ),
        primary_label="Review income & spending →",
        score=(
            abs(signal.remaining) + 100_000
            if signal.overspent else signal.amount_drop
        ),
        evidence=(
            f"Current income: {_money(signal.income)}",
            f"Current all-card personal spending: {_money(signal.spending)}",
            *(
                f"{_month(month)} · {_money(row.remaining)} left · "
                f"{row.remaining_percentage:.1f}%"
                for month in signal.comparison_months
                for row in (dataset.household_history.get(month),)
                if row is not None
            ),
        ),
    )


def _category_finding(signal, month: str) -> ObservationFinding:
    previous = tuple(_shift_month(month, offset) for offset in (-1, -2, -3))
    return ObservationFinding(
        observation_type=signal.observation_type,
        month=month,
        label=signal.category,
        title=f"{signal.category} spending increased",
        description=(
            f"Routine category spending reached {_money(signal.current_amount)}, "
            f"compared with a {_money(signal.baseline)} median across the previous three months."
        ),
        value=_money(signal.current_amount),
        comparison=_money(signal.baseline),
        comparison_detail=(
            f"Three-month routine median across {_range(previous)}; present in at "
            f"least two months and now {signal.routine_share * 100:.1f}% of routine spending."
        ),
        result=f"+{_money(signal.increase)} · {signal.ratio:.1f}×",
        primary_label="Open category activity →",
        score=signal.increase,
        evidence=tuple(
            f"{_month(previous[index])} · {_money(value)}"
            for index, value in enumerate(signal.previous_amounts)
        ) + (
            f"Current routine category spending: {_money(signal.current_amount)}",
            f"Current routine share: {signal.routine_share * 100:.1f}%",
        ),
    )


def _duplicate_finding(
    wrapper: MonthlyDuplicateFinding,
    index: dict[int, MonthlyObservationTransaction],
    month: str,
) -> ObservationFinding:
    signal = wrapper.signal
    rows = tuple(index[value] for value in signal.transaction_ids if value in index)
    date = rows[0].transaction_date if rows else ""
    count = len(signal.transaction_ids)
    return ObservationFinding(
        observation_type="POSSIBLE DUPLICATE",
        month=month,
        label=wrapper.label,
        title=f"{count} matching charges at {wrapper.label}",
        description=(
            "Same original merchant, card, purchase date, charged amount, and currency. "
            "Nothing is removed automatically."
        ),
        value=f"{count} × {_money(signal.charged_amount)}",
        comparison="Merchant + card + date + charged amount",
        result=f"{count} candidates",
        score=signal.charged_amount * count,
        finding_key=signal.finding_key,
        transaction_ids=signal.transaction_ids,
        event_label=_events(rows),
        evidence=(
            f"Transaction IDs: {', '.join(str(value) for value in signal.transaction_ids)}",
            f"Purchase date: {date}",
        ),
    )


def _recurring_finding(
    wrapper: MonthlyRecurringFinding,
    dataset: MonthlyObservationDataset,
    index: dict[int, MonthlyObservationTransaction],
) -> ObservationFinding:
    signal = wrapper.signal
    fee_history, fee_detail = _fee_history(dataset)
    if isinstance(signal, AdditionalRecurringChargeSignal):
        rows = tuple(index[value] for value in signal.transaction_ids if value in index)
        return ObservationFinding(
            observation_type=signal.observation_type,
            month=dataset.month,
            label=wrapper.label,
            title=f"{signal.charge_count} charges near one {wrapper.label} billing window",
            description=(
                "Exact alias and card charges fall within seven days of the learned "
                f"{signal.expected_date} occurrence."
            ),
            value=f"{signal.charge_count} charges",
            comparison="One expected monthly occurrence",
            result=f"{signal.additional_count} additional",
            score=signal.total_amount,
            finding_key=signal.finding_key,
            transaction_ids=signal.transaction_ids,
            recurring_series_id=wrapper.series_id,
            occurrence_start=signal.occurrence_start,
            occurrence_end=signal.occurrence_end,
            event_label=_events(rows),
            evidence=tuple(
                f"{row.transaction_date} · {_money(row.personal_amount)} · transaction {row.id}"
                for row in rows
            ),
        )

    transaction_id = signal.transaction_id
    current = index.get(transaction_id)
    event_label = current.event_name if current else ""
    if isinstance(signal, FirstFeeSignal):
        return ObservationFinding(
            observation_type=signal.observation_type,
            month=dataset.month,
            label=wrapper.label,
            title=f"First fee observed from {wrapper.label}",
            description=(
                "No matching earlier fee was found in the imported lookback. It is "
                "not called new until complete statement coverage can be verified."
            ),
            value=_money(signal.observed_amount),
            comparison=fee_history,
            comparison_detail=fee_detail,
            result="First time found in imported data",
            score=signal.observed_amount,
            event_label=event_label,
            evidence=(
                f"History searched: {fee_history}",
                f"Observed charge: {signal.transaction_date} · {_money(signal.observed_amount)}",
                f"Transaction ID: {transaction_id}",
            ),
        )

    assert isinstance(signal, RecurringAmountSignal)
    formatter = (
        (lambda value: _money(value))
        if signal.comparison_currency == "ILS" else
        (lambda value: _currency_money(value, signal.comparison_currency))
    )
    comparison_rows = tuple(
        index[value] for value in signal.comparison_charge_ids if value in index
    )
    comparison = (
        formatter(signal.baseline)
        if signal.fixed else
        f"{formatter(signal.observed_minimum)}–{formatter(signal.observed_maximum)}"
    )
    return ObservationFinding(
        observation_type=signal.observation_type,
        month=dataset.month,
        label=wrapper.label,
        title=f"{wrapper.label} amount increased",
        description=(
            "Compared with the established recent baseline."
            if signal.fixed else
            "The current amount is above the recent observed range."
        ),
        value=formatter(signal.observed_amount),
        comparison=comparison,
        comparison_label="Baseline" if signal.fixed else "Recent range",
        comparison_detail=(
            (
                f"Median of previous {len(signal.comparison_charge_ids)} matching charges · "
                if signal.fixed else
                f"Range across {len(signal.comparison_charge_ids)} prior matching charges · "
            )
            + _range(tuple(row.transaction_date[:7] for row in comparison_rows))
        ),
        result=f"+{formatter(signal.increase_above_comparison)}",
        score=signal.observed_amount - signal.baseline,
        event_label=event_label,
        evidence=tuple(
            "Baseline · " + row.transaction_date + " · " + formatter(
                row.original_amount
                if signal.comparison_currency != "ILS" and row.original_amount is not None
                else row.personal_amount
            )
            for row in comparison_rows
        ) + (
            f"Observed · {current.transaction_date if current else ''} · {formatter(signal.observed_amount)}",
            f"Transaction ID: {transaction_id}",
        ),
    )


def _merchant_finding(
    wrapper: MonthlyMerchantActivityFinding,
) -> ObservationFinding:
    signal = wrapper.signal
    count_text = (
        str(int(signal.baseline_count))
        if signal.baseline_count.is_integer() else f"{signal.baseline_count:.1f}"
    )
    return ObservationFinding(
        observation_type=signal.observation_type,
        month=signal.current_month,
        label=wrapper.label,
        title=f"{wrapper.label} activity increased",
        description=(
            f"Outside projects and events, this month has {signal.current_count} purchases "
            f"totaling {_money(signal.current_total)}; the comparison uses prior active months only."
        ),
        value=f"{_money(signal.current_total)} · {signal.current_count} purchases",
        comparison=(
            f"{_money(signal.baseline_total)}/month · "
            f"{count_text} purchases/month"
        ),
        comparison_detail=(
            "Separate medians for monthly spend and purchase count across "
            f"{len(signal.active_history)} routine active months · "
            f"{_range(tuple(row.month for row in signal.active_history))}"
        ),
        result=(
            f"{signal.spending_ratio:.1f}× spending baseline"
            if signal.spending_changed else
            f"{signal.purchase_count_ratio:.1f}× purchase-count baseline"
        ),
        score=signal.current_total - signal.baseline_total,
        evidence=tuple(
            f"{_month(row.month)} · {row.purchase_count} purchases · {_money(row.total)}"
            for row in signal.active_history
        ) + (
            f"Current routine month · {signal.current_count} purchases · {_money(signal.current_total)}",
        ),
    )


def _purchase_finding(
    wrapper: MonthlyPurchaseFinding,
    index: dict[int, MonthlyObservationTransaction],
    month: str,
) -> ObservationFinding:
    signal = wrapper.signal
    transaction = index.get(signal.transaction_id)
    unusual = signal.observation_type in {
        "UNUSUAL TRANSACTION", "LARGE AND UNUSUAL PURCHASE",
    }
    large = signal.observation_type != "UNUSUAL TRANSACTION"
    if large and unusual:
        description = (
            f"This is {signal.monthly_share * 100:.1f}% of monthly personal spending "
            f"and {signal.ratio_to_median:.1f}× its stable six-month median."
        )
    elif large:
        description = (
            f"This is {signal.monthly_share * 100:.1f}% of positive personal spending. "
            "Both thresholds were met."
        )
    else:
        baseline = signal.baseline
        description = (
            f"Compared with {baseline.purchase_count} earlier purchases across "
            f"{baseline.month_count} months; {baseline.inside_band_count} fell within "
            "±30% of the median."
        )
    return ObservationFinding(
        observation_type=signal.observation_type,
        month=month,
        label=wrapper.label,
        title=(
            f"Unusual transaction at {wrapper.label}"
            if signal.observation_type == "UNUSUAL TRANSACTION" else
            f"Large purchase at {wrapper.label}"
        ),
        description=description,
        value=_money(signal.amount),
        comparison=(
            f"{_money(signal.baseline.median)} six-month median"
            if unusual and signal.baseline else
            f"{_money(signal.monthly_total)} monthly personal spending"
        ),
        result=(
            f"{signal.ratio_to_median:.1f}× median"
            if unusual else f"{signal.monthly_share * 100:.1f}% of month"
        ),
        score=signal.amount,
        finding_key=signal.finding_key or "",
        transaction_ids=(signal.transaction_id,) if signal.finding_key else (),
        event_label=transaction.event_name if transaction else "",
        evidence=(
            f"Personal amount: {_money(signal.amount)}",
            f"Original card charge: {_money(transaction.charged_amount if transaction else 0)}",
            f"Transaction ID: {signal.transaction_id}",
        ),
    )


def _standalone_fee_finding(
    wrapper: MonthlyStandaloneFeeFinding,
    dataset: MonthlyObservationDataset,
    index: dict[int, MonthlyObservationTransaction],
) -> ObservationFinding:
    signal = wrapper.signal
    history, detail = _fee_history(dataset)
    transaction = index.get(signal.transaction_id)
    return ObservationFinding(
        observation_type=signal.observation_type,
        month=dataset.month,
        label=wrapper.label,
        title=f"First fee observed from {wrapper.label}",
        description=(
            "No matching fee appears in the imported 12-month lookback. It is not "
            "called new until complete coverage can be verified."
        ),
        value=_money(signal.observed_amount),
        comparison=history,
        comparison_detail=detail,
        result="First time found in imported data",
        score=signal.observed_amount,
        event_label=transaction.event_name if transaction else "",
        evidence=(
            f"History searched: {history}",
            f"Observed charge: {signal.transaction_date} · {_money(signal.observed_amount)}",
            f"Transaction ID: {signal.transaction_id}",
        ),
    )


def monthly_findings(
    analysis: MonthlyObservationAnalysis,
    dataset: MonthlyObservationDataset,
) -> tuple[ObservationFinding, ...]:
    """Map qualified monthly signals without recalculating eligibility."""
    findings: list[ObservationFinding] = []
    index = _transaction_index(dataset)
    amount_left = _amount_left_finding(analysis, dataset)
    if amount_left is not None:
        findings.append(amount_left)
    findings.extend(
        _category_finding(signal, dataset.month)
        for signal in analysis.category_spending
    )
    findings.extend(
        _duplicate_finding(wrapper, index, dataset.month)
        for wrapper in analysis.possible_duplicates
    )
    findings.extend(
        _recurring_finding(wrapper, dataset, index)
        for wrapper in analysis.recurring_findings
    )
    findings.extend(_merchant_finding(wrapper) for wrapper in analysis.merchant_activity)
    findings.extend(
        _purchase_finding(wrapper, index, dataset.month)
        for wrapper in analysis.purchases
    )
    findings.extend(
        _standalone_fee_finding(wrapper, dataset, index)
        for wrapper in analysis.standalone_fees
    )
    return tuple(findings)


def monthly_observation_groups(
    analysis: MonthlyObservationAnalysis,
    dataset: MonthlyObservationDataset,
    reviewed_finding_keys: tuple[str, ...] = (),
) -> tuple[ObservationGroup, ...]:
    """Create active monthly cards through the shared grouping boundary."""
    return assemble_active_observation_groups(
        monthly_findings(analysis, dataset), reviewed_finding_keys,
    )
