"""Installment evidence validation, progression, and reconciliation."""

from __future__ import annotations

from collections import defaultdict

from clearspend.recurring.forecast_common import (
    actual_occurrence,
    card_dict,
    estimated_date,
    is_ils,
    median,
    money,
    single_evidence_card,
)
from clearspend.recurring.forecast_models import (
    ChargeEvidence,
    InstallmentForecastEvidence,
    InternalOccurrence,
    UnresolvedForecast,
)
from clearspend.recurring.identity import (
    installment_occurrence_identity,
    unexpected_actual_identity,
)
from clearspend.reporting.periods import shift_month


def installment_occurrences(
    plan: InstallmentForecastEvidence, anchor_month: str, horizon_end: str,
) -> tuple[list[InternalOccurrence], list[UnresolvedForecast]]:
    baseline_start = shift_month(anchor_month, -24)
    baseline = sorted(
        (item for item in plan.charges if baseline_start <= item.report_month < anchor_month),
        key=lambda item: (item.report_month, item.installment_number or 0, item.transaction_key),
    )
    horizon = sorted(
        (item for item in plan.charges if anchor_month <= item.report_month <= horizon_end),
        key=lambda item: (item.report_month, item.installment_number or 0, item.transaction_key),
    )
    def valid_evidence(item: ChargeEvidence) -> bool:
        return bool(
            item.installment_number is not None
            and item.installment_total is not None
            and 1 <= item.installment_number <= item.installment_total
        )

    valid = [item for item in baseline if valid_evidence(item)]
    valid_horizon = [item for item in horizon if valid_evidence(item)]
    invalid_baseline = [item for item in baseline if not valid_evidence(item)]
    invalid_horizon = [item for item in horizon if not valid_evidence(item)]
    totals = {
        item.installment_total for item in [*valid, *valid_horizon]
        if item.installment_total is not None
    }
    baseline_numbers = [item.installment_number for item in valid]
    inconsistent = len(totals) > 1 or len(baseline_numbers) != len(set(baseline_numbers))
    unresolved: list[UnresolvedForecast] = []
    if invalid_baseline or invalid_horizon or inconsistent:
        evidence_card = single_evidence_card([*baseline, *horizon])
        unresolved.append({
            "source_kind": "installment_plan",
            "source_id": plan.commitment_id,
            "display_name": plan.display_name,
            "card": card_dict(evidence_card) if evidence_card else None,
            "reason": "invalid_installment_evidence",
        })
    actual_groups: dict[int | None, list[ChargeEvidence]] = defaultdict(list)
    for actual in horizon:
        actual_groups[actual.installment_number].append(actual)
    output: list[InternalOccurrence] = []
    consumed: set[int | None] = set()

    progress_rows = list(valid)
    current = max((item.installment_number or 0 for item in valid), default=0)
    total = next(iter(totals), 0) if len(totals) == 1 else 0
    card = valid[-1].card if valid else ""
    next_month = anchor_month

    if not valid and not invalid_baseline and not inconsistent:
        anchor_rows = [
            item for item in valid_horizon if item.report_month == anchor_month
        ]
        if len(anchor_rows) == 1:
            seed = anchor_rows[0]
            current = seed.installment_number or 0
            total = seed.installment_total or 0
            card = seed.card
            progress_rows = [seed]
            next_month = shift_month(anchor_month, 1)
            consumed.add(seed.installment_number)
            output.append(actual_occurrence(
                seed,
                occurrence_id=installment_occurrence_identity(
                    plan.commitment_id, current,
                ),
                display_name=plan.display_name,
                payment_type="Installment",
                status="confirmed",
                ending=current == total,
            ))

    can_project = bool(progress_rows and total and not invalid_baseline and not inconsistent)
    if can_project:
        amount_rows = [item for item in progress_rows if item.amount > 0]
        amounts = (
            [item.amount for item in amount_rows]
            if all(is_ils(item.charged_currency) for item in amount_rows)
            else []
        )
        amount = median(amounts) if amounts else None
        for installment_number in range(current + 1, total + 1):
            actuals = actual_groups.get(installment_number, [])
            if len(actuals) > 1:
                for actual in actuals:
                    output.append(actual_occurrence(
                        actual,
                        occurrence_id=unexpected_actual_identity(
                            actual.transaction_key,
                        ),
                        display_name=plan.display_name,
                        payment_type="Installment",
                        status="unexpected_actual",
                        ending=(actual.installment_number == actual.installment_total),
                    ))
                consumed.add(installment_number)
                break
            if len(actuals) == 1:
                actual = actuals[0]
                if actual.report_month < next_month:
                    continue
                output.append(actual_occurrence(
                    actual,
                    occurrence_id=installment_occurrence_identity(
                        plan.commitment_id, installment_number,
                    ),
                    display_name=plan.display_name,
                    payment_type="Installment",
                    status=(
                        "confirmed" if actual.card == card else "unexpected_card"
                    ),
                    ending=installment_number == total,
                ))
                consumed.add(installment_number)
                next_month = shift_month(actual.report_month, 1)
                continue
            if next_month > horizon_end:
                break
            expected_date = estimated_date(progress_rows, next_month)
            output.append({
                "occurrence_id": installment_occurrence_identity(
                    plan.commitment_id, installment_number,
                ),
                "expected_date": expected_date,
                "date_evidence": "estimated" if expected_date else "month_only",
                "display_name": plan.display_name,
                "card": card_dict(card),
                "payment_type": "Installment",
                "amount": money(amount) if amount is not None else None,
                "amount_evidence": "estimate" if amount is not None else "unknown",
                "amount_confidence": "established" if amount is not None else None,
                "occurrence_status": "expected",
                "recent_range": None,
                "installment_number": installment_number,
                "installment_total": total,
                "annual": False,
                "ending": installment_number == total,
                "_month": next_month,
                "_logical_card": card,
            })
            next_month = shift_month(next_month, 1)

    for installment_number, actuals in actual_groups.items():
        if installment_number in consumed:
            continue
        for actual in actuals:
            output.append(actual_occurrence(
                actual,
                occurrence_id=unexpected_actual_identity(actual.transaction_key),
                display_name=plan.display_name,
                payment_type="Installment",
                status="unexpected_actual",
                ending=(actual.installment_number == actual.installment_total),
            ))
    return output, unresolved
