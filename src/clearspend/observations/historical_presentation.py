"""Presentation mapping for qualified long-period observation signals."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP

from clearspend.observations.grouping import (
    ObservationFinding,
    ObservationGroup,
    assemble_active_observation_groups,
)
from clearspend.observations.historical_analysis import (
    HistoricalObservationAnalysis,
)
from clearspend.observations.historical_merchant_rules import (
    EstablishedMerchantHabitShift,
    RegularMerchantHabit,
)
from clearspend.observations.historical_rules import (
    AmountLeftTrend,
    CategoryRoutineShift,
    PersistentInstallmentBurden,
    RecurringBurdenShift,
    SpendingRoutineShift,
)


def _money(value: float) -> str:
    rounded = Decimal(str(float(value))).quantize(
        Decimal("0.01"), rounding=ROUND_HALF_UP,
    )
    return f"₪{rounded:,.2f}"


def _month(value: str) -> str:
    try:
        label = datetime.strptime(value, "%Y-%m").strftime("%b %Y")
        return label.replace("Sep ", "Sept ")
    except (TypeError, ValueError):
        return str(value or "")


def _range(months: tuple[str, ...]) -> str:
    if not months:
        return ""
    return _month(months[0]) if len(months) == 1 else f"{_month(months[0])} – {_month(months[-1])}"


def _status(active: bool, duration: int) -> str:
    return "still visible" if active else f"lasted {duration} months"


def _shift_month(value: str, offset: int) -> str:
    year, month = (int(part) for part in value.split("-", 1))
    number = year * 12 + month - 1 + offset
    return f"{number // 12:04d}-{number % 12 + 1:02d}"


def _signed_money(value: float) -> str:
    return f"{'+' if value >= 0 else '−'}{_money(abs(value))}"


def _signed_number(value: float, suffix: str = "") -> str:
    return f"{'+' if value >= 0 else '−'}{abs(value):.1f}{suffix}"


def _spending_finding(signal: SpendingRoutineShift) -> ObservationFinding:
    status = _status(signal.active, signal.duration)
    direction = "higher" if signal.higher else "lower"
    side = "above" if signal.higher else "below"
    return ObservationFinding(
        observation_type=signal.observation_type,
        month=signal.start_month,
        label="Overall spending",
        entity_label="Overall spending",
        entity_sublabel=f"{_month(signal.start_month)} · {status}",
        title=f"Monthly spending shifted {direction} in {_month(signal.start_month)}",
        description=(
            "Outside projects and events, at least two of the first three months "
            f"individually cleared both change thresholds, and all three stayed {side} "
            "the earlier baseline."
        ),
        value=_money(signal.post_average),
        comparison=_money(signal.baseline),
        comparison_detail=(
            "Event-assigned purchases were excluded. Post-change average for "
            f"{_range(signal.post_months)} compared with the median of "
            f"{_range(signal.pre_months)}. At least two post-change months individually "
            "had to differ by both 20% and ₪1,000, while all three had to remain "
            "on the same side."
        ),
        result=(
            f"{_signed_money(signal.difference)} · "
            f"{_signed_number(signal.change_percentage, '%')} · {status}"
        ),
        card_summary="",
        card_comparison_primary=(
            f"{_money(signal.post_average)}/month vs {_money(signal.baseline)} baseline"
        ),
        card_comparison_secondary=(
            f"{_signed_money(signal.difference)} · "
            f"{_signed_number(signal.change_percentage, '%')} · "
            f"began {_month(signal.start_month)} · {status}"
        ),
        rule_text=(
            "Event-assigned purchases were excluded. At least two of the first "
            "three months cleared both the 20% and ₪1,000 thresholds individually, "
            f"and all three stayed {side} the earlier median."
        ),
        score=signal.score,
        evidence=tuple(
            f"{_month(month)} · {_money(value)}"
            for month, value in (
                *zip(signal.pre_months, signal.pre_values),
                *zip(signal.post_months, signal.post_values),
            )
        ),
    )


def _amount_left_finding(signal: AmountLeftTrend) -> ObservationFinding:
    status = _status(signal.active, signal.duration)
    common = {
        "observation_type": signal.observation_type,
        "month": signal.start_month,
        "label": "Income and spending",
        "entity_label": "Income and spending",
        "entity_sublabel": f"{_month(signal.start_month)} · {status}",
        "score": signal.score,
        "card_summary": "",
    }
    if signal.kind == "repeated_overspending":
        return ObservationFinding(
            **common,
            title="Spending exceeded income repeatedly",
            description=(
                f"Spending exceeded income in {signal.overspent_months} of the first "
                "three months after the shift."
            ),
            value=f"{signal.overspent_months} of 3 months",
            comparison="Monthly income",
            comparison_detail=(
                "Compared income and all-card personal spending using the same fully covered months."
            ),
            result=f"{_money(signal.average_shortfall or 0)} average shortfall",
            evidence=tuple(
                f"{_month(row.month)} · income {_money(row.income)} · spending {_money(row.spending)}"
                for row in signal.post_rows
            ),
        )
    if signal.kind == "spending_outgrew_income":
        spending_growth = (signal.spending_growth or 0) * 100
        income_growth = (signal.income_growth or 0) * 100
        gap = (signal.growth_gap or 0) * 100
        return ObservationFinding(
            **common,
            title="Spending grew faster than income",
            description=(
                f"Since {_month(signal.start_month)}, spending has grown materially "
                f"faster than income and the gap is {status}."
            ),
            value=_signed_number(spending_growth, "%"),
            value_label="Spending growth",
            comparison=_signed_number(income_growth, "%"),
            comparison_label="Income growth",
            comparison_detail=(
                f"Average income and spending for {_range(signal.post_months)} were "
                f"compared with their medians for {_range(signal.pre_months)}. Only "
                "months with both income and all-card spending coverage were used; "
                "both baselines were above zero."
            ),
            result=f"{gap:.1f} percentage-point gap",
            result_label="Growth gap",
            card_comparison_primary=(
                f"Spending {_signed_number(spending_growth, '%')} · "
                f"Income {_signed_number(income_growth, '%')}"
            ),
            card_comparison_secondary=(
                f"Gap {gap:.1f} pp · began {_month(signal.start_month)} · {status}"
            ),
            rule_text=(
                f"Spending increased by {spending_growth:.1f}%, income increased by "
                f"{income_growth:.1f}%, and the {gap:.1f} percentage-point gap "
                "exceeded the 10-point threshold."
            ),
            evidence=(
                f"Income · {_money(signal.baseline_income or 0)} → {_money(signal.post_income or 0)}",
                f"Spending · {_money(signal.baseline_spending or 0)} → {_money(signal.post_spending or 0)}",
            ),
        )
    amount_change = signal.amount_change or 0
    percentage_change = signal.percentage_point_change or 0
    direction = "higher" if amount_change > 0 else "lower"
    return ObservationFinding(
        **common,
        title=f"The amount left shifted {direction}",
        description="The shekel amount and percentage of income moved in the same direction.",
        value=f"{_money(signal.post_left or 0)} · {(signal.post_percentage or 0):.1f}% left",
        comparison=(
            f"{_money(signal.baseline_left or 0)} · "
            f"{(signal.baseline_percentage or 0):.1f}% left"
        ),
        comparison_detail=(
            "Used matching fully covered income and spending months; mixed-direction "
            "changes are kept only in the evidence."
        ),
        result=(
            f"{_signed_money(amount_change)} · "
            f"{abs(percentage_change):.1f} pp"
        ),
        evidence=tuple(
            f"{_month(row.month)} · {_money(row.amount_left)} left · {row.percentage_left:.1f}%"
            for row in signal.post_rows
        ),
    )


def _category_finding(signal: CategoryRoutineShift) -> ObservationFinding:
    status = _status(signal.active, signal.duration)
    direction = "higher" if signal.higher else "lower"
    difference = signal.post_average - signal.baseline
    return ObservationFinding(
        observation_type=signal.observation_type,
        month=signal.start_month,
        label=signal.category,
        entity_sublabel=f"{_month(signal.start_month)} · {status}",
        pattern_period=(
            f"{_month(signal.start_month)} – present" if signal.active
            else f"{_month(signal.start_month)} – "
            f"{_month(_shift_month(signal.start_month, signal.duration - 1))}"
        ),
        title=(
            f"{signal.category} spending shifted {direction} in {_month(signal.start_month)}"
        ),
        description=(
            "Outside projects and events, covered months with no category spending "
            "count as zero. "
            + (
                f"Main merchants in the compared period: {', '.join(signal.drivers)}."
                if signal.drivers else ""
            )
        ),
        value=_money(signal.post_average),
        comparison=_money(signal.baseline),
        comparison_detail=(
            "Event-assigned purchases were excluded. Post-change average for "
            f"{_range(signal.post_months)} versus the pre-change monthly median for "
            f"{_range(signal.pre_months)}. This is a shekel-spending comparison, "
            "not a category-share claim."
        ),
        result=(
            f"{_signed_money(difference)} · "
            f"{'still visible' if signal.active else f'{signal.duration} months'}"
        ),
        score=signal.score,
        evidence=tuple(
            [
                *(f"{_month(month)} · {_money(value)}" for month, value in zip(
                    signal.post_months, signal.post_values,
                )),
                f"Merchant drivers · {' · '.join(signal.drivers) or 'No merchant detail'}",
            ]
        ),
    )


def _recurring_finding(signal: RecurringBurdenShift) -> ObservationFinding:
    cost_change = signal.cost_after - signal.cost_baseline
    count_change = signal.count_after - signal.count_baseline
    cost_percent = cost_change / signal.cost_baseline * 100 if signal.cost_baseline else 0
    status = _status(signal.active, signal.duration)
    if signal.cost_shift and signal.count_shift:
        title = "Monthly commitments changed in cost while service count also changed"
    elif signal.count_shift:
        title = "The number of ongoing services changed"
    else:
        title = f"Monthly commitment cost {'increased' if cost_change >= 0 else 'decreased'}"
    result = (
        f"{_signed_money(cost_change)}/month · {_signed_number(cost_percent, '%')}"
        if signal.cost_shift else f"{_signed_number(count_change)} services"
    )
    return ObservationFinding(
        observation_type=signal.observation_type,
        month=signal.start_month,
        label="Recurring commitments",
        entity_label="Recurring commitments",
        entity_sublabel=f"{_month(signal.start_month)} · {status}",
        title=f"{title} in {_month(signal.start_month)}",
        description=(
            "Your normalized recurring and scheduled monthly burden moved from "
            f"{_money(signal.cost_baseline)} to {_money(signal.cost_after)}. Service "
            "count is shown alongside cost so one large service is not treated like "
            "several small ones."
        ),
        value=f"{_money(signal.cost_after)}/month · {signal.count_after:.1f} services",
        comparison=(
            f"{_money(signal.cost_baseline)}/month · {signal.count_baseline:.1f} services"
        ),
        comparison_detail=(
            f"Compared the post-change average for {_range(signal.post_months)} with "
            f"the pre-change monthly median for {_range(signal.pre_months)}. "
            "Non-monthly schedules were converted to monthly equivalents—for "
            "example, an annual ₪1,200 obligation contributes ₪100 per month."
        ),
        result=result,
        result_label="Cost change" if signal.cost_shift else "Service-count change",
        card_summary="",
        card_comparison_primary=(
            f"{_money(signal.cost_after)}/month vs {_money(signal.cost_baseline)} baseline"
        ),
        card_comparison_secondary=(
            f"{result} · {signal.count_after:.1f} vs {signal.count_baseline:.1f} services"
        ),
        rule_text=(
            "The normalized monthly cost changed by "
            f"{_money(abs(cost_change))} ({abs(cost_percent):.1f}%) and/or the "
            f"active-service count changed by {abs(count_change):.1f}, crossing "
            "the recurring-burden threshold."
        ),
        score=signal.score,
        evidence=(
            *(
                f"{_month(month)} · {_money(cost)}/month · {count:g} services"
                for month, cost, count in zip(
                    signal.post_months, signal.post_costs, signal.post_counts,
                )
            ),
            f"Started · {', '.join(signal.started) or 'None'}",
            f"Ended · {', '.join(signal.ended) or 'None'}",
            *(f"{item.name} changed · {_money(item.before)}/month → {_money(item.after)}/month"
              for item in signal.changed),
        ),
    )


def _installment_finding(signal: PersistentInstallmentBurden) -> ObservationFinding:
    status = _status(signal.active, signal.duration)
    return ObservationFinding(
        observation_type=signal.observation_type,
        month=signal.start_month,
        label="Installment plans",
        entity_label="Installment plans",
        entity_sublabel=f"{_month(signal.start_month)} · {status}",
        title=(
            "Ending installment plans were repeatedly replaced"
            if signal.replacements else "Installment payments stayed persistently high"
        ),
        description=(
            "New individual plans repeatedly replaced plans that ended, preventing "
            "the monthly installment burden from falling."
            if signal.replacements else
            "The burden remained material even without requiring evidence that new "
            "plans replaced ending plans."
        ),
        value=f"{_money(signal.average_burden)}/month",
        comparison=f"{signal.duration} consecutive months",
        comparison_label="Duration",
        comparison_detail=(
            "A persistent burden requires at least six consecutive months, a minimum "
            "monthly amount of ₪500, and an average of at least ₪1,000. Replacement "
            "is a separate explanation based on individual plan identity."
        ),
        result=(
            f"{signal.starts} starts · {signal.endings} endings"
            if signal.replacements else "Persistent burden only"
        ),
        score=signal.score,
        evidence=tuple(
            f"{_month(month)} · {_money(value)} · {count} plans"
            for month, value, count in zip(
                signal.months, signal.burdens, signal.plan_counts,
            )
        ),
    )


def _regular_merchant_finding(signal: RegularMerchantHabit) -> ObservationFinding:
    if signal.later_months < 2:
        status = "recently established"
    elif signal.still_visible:
        status = "still visible"
    else:
        status = "not visible in most recent months"
    qualification = (
        "spending and frequency" if signal.spending_qualified and signal.frequency_qualified
        else "monthly spending" if signal.spending_qualified else "purchase frequency"
    )
    return ObservationFinding(
        observation_type=signal.observation_type,
        month=signal.start_month,
        label=signal.merchant_label,
        entity_sublabel=f"{_month(signal.start_month)} · {status}",
        habit_kind="Merchant became regular",
        title=f"Merchant became regular: {signal.merchant_label}",
        description=(
            f"{signal.purchase_count} purchases across {_range(signal.establishment_months)}, "
            f"averaging {_money(signal.average_monthly_spending)} per month. "
            + (
                f"Activity continued in {signal.later_active_months} of the following "
                f"{signal.later_months} complete months."
                if signal.later_months else
                "The establishment period reaches the end of the selected history."
            )
            + (" Purchase frequency later increased further." if signal.buying_more else "")
        ),
        value=(
            f"{signal.established_frequency:.1f} purchases/month · "
            f"{_money(signal.average_monthly_spending)}/month"
        ),
        comparison=(
            f"Active in {signal.prior_active_months} of {len(signal.pre_months)} months"
        ),
        comparison_detail=(
            f"Purchase dates were used. The merchant qualified through {qualification}: "
            "three consecutive active months or four of six were required, with "
            "little earlier activity. Reviewed recurring aliases, installments, "
            "and money transfers were excluded."
        ),
        result=(
            f"Now {signal.recent_frequency:.1f}/month · {status}"
            if signal.buying_more else
            f"{signal.later_active_months} of {signal.later_months} later months · {status}"
            if signal.later_months else "Established at period end"
        ),
        card_summary="",
        card_comparison_primary=(
            f"{signal.purchase_count} purchases · {_money(signal.average_monthly_spending)}/month"
        ),
        card_comparison_secondary=(
            f"Began {_month(signal.start_month)} · {status}"
            + (
                f" · now {signal.recent_frequency:.1f} purchases/month"
                if signal.buying_more else ""
            )
        ),
        rule_text=(
            f"This merchant became regular through {qualification}. Spending "
            "qualifies at ₪200 per month; frequency qualifies with at least six "
            "purchases across three consecutive months on multiple purchase days."
        ),
        score=signal.score,
        evidence=(
            *(
                f"{_month(month)} · {count} purchases · {_money(amount)}"
                for month, count, amount in zip(
                    signal.establishment_months,
                    signal.establishment_purchase_counts,
                    signal.monthly_spending,
                )
            ),
            *(
                f"{_month(month)} recent · {count} purchases · {_money(amount)}"
                for month, count, amount in zip(
                    signal.recent_months,
                    signal.recent_purchase_counts,
                    signal.recent_spending,
                )
            ),
        ),
    )


def _merchant_shift_finding(
    signal: EstablishedMerchantHabitShift,
) -> ObservationFinding:
    frequency = signal.kind in {"Buying more often", "Buying less often"}
    after = signal.post_count if frequency else signal.post_typical_amount
    before = signal.pre_count if frequency else signal.pre_typical_amount
    change = after - before
    ratio = after / before if before else 0
    status = _status(signal.active, signal.duration)
    return ObservationFinding(
        observation_type=signal.observation_type,
        month=signal.start_month,
        label=signal.merchant_label,
        entity_sublabel=f"{_month(signal.start_month)} · {status}",
        habit_kind=signal.kind,
        title=f"{signal.kind}: {signal.merchant_label}",
        description=f"Detected a sustained purchase-date change beginning in {_month(signal.start_month)}.",
        value=(f"{after:.1f} purchases/month" if frequency else _money(after)),
        comparison=(f"{before:.1f} purchases/month" if frequency else _money(before)),
        comparison_detail=(
            "Purchase frequency and median purchase amount were evaluated separately "
            "before and after the candidate change month. Reviewed recurring aliases, "
            "installments, and money transfers were excluded."
        ),
        result=(
            f"{_signed_number(change)}/month · {ratio:.1f}× · {status}"
            if frequency else f"{_signed_money(change)} · {ratio:.1f}× · {status}"
        ),
        score=signal.score,
        evidence=tuple(
            f"{_month(month)} · {count} purchases · {_money(spending)}"
            for month, count, spending in zip(
                signal.post_months, signal.post_counts, signal.post_spending,
            )
        ),
    )


def historical_findings(
    analysis: HistoricalObservationAnalysis,
) -> tuple[ObservationFinding, ...]:
    """Map qualified signals without recalculating their eligibility."""
    findings: list[ObservationFinding] = []
    if analysis.amount_left:
        findings.append(_amount_left_finding(analysis.amount_left))
    if analysis.spending_routine:
        findings.append(_spending_finding(analysis.spending_routine))
    if analysis.recurring_burden:
        findings.append(_recurring_finding(analysis.recurring_burden))
    if analysis.installment_burden:
        findings.append(_installment_finding(analysis.installment_burden))
    findings.extend(_category_finding(signal) for signal in analysis.category_routines)
    merchant_findings = [
        *(_regular_merchant_finding(signal) for signal in analysis.newly_regular_merchants),
        *(_merchant_shift_finding(signal) for signal in analysis.merchant_habit_shifts),
    ]
    findings.extend(sorted(merchant_findings, key=lambda item: -item.score)[:12])
    return tuple(findings)


def historical_observation_groups(
    analysis: HistoricalObservationAnalysis,
    reviewed_finding_keys: tuple[str, ...] = (),
) -> tuple[ObservationGroup, ...]:
    """Create active card groups through the shared grouping boundary."""
    return assemble_active_observation_groups(
        historical_findings(analysis), reviewed_finding_keys,
    )
