"""Recurring schedule, amount confidence, card resolution, and reconciliation."""

from __future__ import annotations

from collections import Counter, defaultdict
from datetime import date
from decimal import Decimal
from typing import Sequence

from clearspend.recurring.forecast_common import (
    actual_occurrence,
    card_dict,
    confirmed_date,
    date_day,
    estimated_date,
    is_ils,
    median,
    money,
    single_evidence_card,
)
from clearspend.recurring.forecast_models import (
    ChargeEvidence,
    InternalOccurrence,
    RecurringForecastEvidence,
    UnresolvedForecast,
)
from clearspend.recurring.identity import (
    recurring_occurrence_identity,
    recurring_series_identity,
    unexpected_actual_identity,
)
from clearspend.recurring.rules import CADENCE_MONTHS, canonical_cadence
from clearspend.reporting.periods import month_number, shift_month


SUPPORTED_CADENCE_MONTHS = frozenset({1, 2, 3, 6, 12})


def _schedule_phase(
    charges: Sequence[ChargeEvidence], cadence_months: int, *, reviewed_monthly: bool = False,
) -> tuple[int | None, str | None]:
    months = sorted({item.report_month for item in charges})
    if cadence_months not in SUPPORTED_CADENCE_MONTHS:
        return None, "unsupported_cadence"
    if reviewed_monthly and cadence_months == 1 and months:
        return 0, None
    minimum = 2 if cadence_months in {6, 12} else 3
    if len(months) < minimum:
        return None, "insufficient_schedule_history"
    if cadence_months in {1, 2, 3}:
        support = Counter(month_number(value) % cadence_months for value in months)
        most = support.most_common()
        if not most or most[0][1] < 2:
            return None, "insufficient_schedule_history"
        if len(most) > 1 and most[0][1] == most[1][1]:
            return None, "ambiguous_phase"
        return most[0][0], None

    candidates: list[tuple[str, int]] = []
    for left, right in zip(months, months[1:]):
        gap = month_number(right) - month_number(left)
        if abs(gap - cadence_months) <= 1:
            candidates.append((right, month_number(right) % cadence_months))
    if not candidates:
        return None, "insufficient_schedule_history"
    return candidates[-1][1], None


def _expected_cycle_months(
    phase: int, cadence_months: int, end_month: str, count: int,
) -> list[str]:
    result: list[str] = []
    current = month_number(end_month)
    while current >= 0 and len(result) < count:
        if current % cadence_months == phase:
            result.append(f"{current // 12:04d}-{current % 12 + 1:02d}")
        current -= 1
    return list(reversed(result))


def _resolve_card_slots(
    charges: Sequence[ChargeEvidence], phase: int, cadence_months: int,
) -> tuple[dict[str, list[ChargeEvidence]] | None, str | None]:
    by_card: dict[str, list[ChargeEvidence]] = defaultdict(list)
    for charge in charges:
        by_card[charge.card].append(charge)
    if len(by_card) == 1:
        card = next(iter(by_card))
        return {card: sorted(by_card[card], key=lambda item: item.report_month)}, None

    end_month = max(item.report_month for item in charges)
    cycles = set(_expected_cycle_months(phase, cadence_months, end_month, 3))
    relevant = {
        card: rows
        for card, rows in by_card.items()
        if any(item.report_month in cycles for item in rows)
    }
    parallel = {
        card: rows
        for card, rows in relevant.items()
        if len({item.report_month for item in rows if item.report_month in cycles}) >= 2
    }
    if len(parallel) == len(relevant) and len(parallel) > 1:
        return {
            card: sorted(rows, key=lambda item: item.report_month)
            for card, rows in parallel.items()
        }, None

    cards_by_month: dict[str, set[str]] = defaultdict(set)
    for charge in charges:
        cards_by_month[charge.report_month].add(charge.card)
    recent_months = sorted(cards_by_month, reverse=True)[:2]
    if len(recent_months) == 2 and all(
        len(cards_by_month[month]) == 1 for month in recent_months
    ):
        recent_cards = {next(iter(cards_by_month[month])) for month in recent_months}
        if len(recent_cards) != 1:
            return None, "ambiguous_card"
        card = recent_cards.pop()
        return {card: sorted(by_card[card], key=lambda item: item.report_month)}, None
    return None, "ambiguous_card"


def _within_fixed_band(value: Decimal, typical: Decimal) -> bool:
    return bool(typical and abs(value - typical) <= typical * Decimal("0.15"))


def _directly_similar_fixed_amounts(left: Decimal, right: Decimal) -> bool:
    smaller, larger = sorted((left, right))
    return bool(smaller > 0 and larger / smaller <= Decimal("1.15"))


def _matching_actual(
    actuals: Sequence[ChargeEvidence], amount: Decimal | float | None,
    expected_date: str | None,
) -> ChargeEvidence | None:
    if len(actuals) == 1:
        return actuals[0]
    if amount is None:
        return None
    typical = Decimal(str(amount))
    amount_matches = [
        item for item in actuals
        if is_ils(item.charged_currency) and _within_fixed_band(item.amount, typical)
    ]
    if len(amount_matches) == 1:
        return amount_matches[0]
    if not expected_date:
        return None
    try:
        expected_day = date.fromisoformat(expected_date[:10]).day
    except ValueError:
        return None
    dated_matches = [
        item for item in amount_matches
        if (day := date_day(confirmed_date(item))) is not None
        and abs(day - expected_day) <= 3
    ]
    return dated_matches[0] if len(dated_matches) == 1 else None


def _fixed_component_match(
    rows: Sequence[ChargeEvidence], typical: Decimal, typical_day: int | None,
) -> ChargeEvidence | None:
    amount_matches = [item for item in rows if _within_fixed_band(item.amount, typical)]
    if len(amount_matches) == 1:
        return amount_matches[0]
    if typical_day is None:
        return None
    dated_matches = [
        item for item in amount_matches
        if (day := date_day(confirmed_date(item))) is not None
        and abs(day - typical_day) <= 3
    ]
    return dated_matches[0] if len(dated_matches) == 1 else None


def _stable_fixed_component(
    by_month: dict[str, list[ChargeEvidence]], recent_months: list[str],
) -> list[ChargeEvidence] | None:
    """Find one uniquely supported fixed component without merging extra charges."""
    candidates: dict[tuple[tuple[str, str], ...], list[ChargeEvidence]] = {}
    for seed in (item for month in recent_months for item in by_month[month]):
        seed_day = date_day(confirmed_date(seed))
        selected: list[ChargeEvidence] = []
        for month in recent_months:
            match = _fixed_component_match(
                by_month[month], seed.amount, seed_day,
            )
            if match is not None:
                selected.append(match)
        if len(selected) < 3:
            continue
        typical = median([item.amount for item in selected])
        selected_days = [
            day for item in selected
            if (day := date_day(confirmed_date(item))) is not None
        ]
        typical_day: int | None = None
        if len(selected_days) >= 3:
            candidate_day = int(median([Decimal(day) for day in selected_days]))
            if all(abs(day - candidate_day) <= 3 for day in selected_days):
                typical_day = candidate_day
        refined: list[ChargeEvidence] = []
        for month in recent_months:
            match = _fixed_component_match(by_month[month], typical, typical_day)
            if match is not None:
                refined.append(match)
        if len(refined) < 3:
            continue
        key = tuple((item.report_month, item.transaction_key) for item in refined)
        candidates[key] = refined

    if not candidates:
        return None

    latest_three = recent_months[-3:]
    consecutive_latest = len(latest_three) == 3 and all(
        shift_month(latest_three[index], 1) == latest_three[index + 1]
        for index in range(2)
    )
    if consecutive_latest:
        suffix_candidates = [
            rows for rows in candidates.values()
            if {item.report_month for item in rows}.issuperset(latest_three)
        ]
        if len(suffix_candidates) == 1:
            return suffix_candidates[0]
        if len(suffix_candidates) > 1:
            return None

    required = len(recent_months) if len(recent_months) <= 4 else len(recent_months) - 1
    reliable = [rows for rows in candidates.values() if len(rows) >= required]
    if not reliable:
        return None
    strongest = max(len(rows) for rows in reliable)
    strongest_candidates = [rows for rows in reliable if len(rows) == strongest]
    return strongest_candidates[0] if len(strongest_candidates) == 1 else None


def _amount_projection(
    recurring_type: str, charges: Sequence[ChargeEvidence],
) -> tuple[Decimal | None, str, list[float] | None, str | None]:
    by_month: dict[str, list[ChargeEvidence]] = defaultdict(list)
    for charge in charges:
        if charge.amount > 0:
            by_month[charge.report_month].append(charge)
    recent_months = sorted(by_month)[-6:]
    recent_charges = [item for month in recent_months for item in by_month[month]]
    if any(not is_ils(item.charged_currency) for item in recent_charges):
        return None, "unknown", None, None
    if recurring_type == "Usage-based recurring":
        monthly_totals = [sum(
            (item.amount for item in by_month[month]), Decimal(0)
        ) for month in recent_months]
        if len(monthly_totals) < 3:
            return None, "unknown", None, None
        return (
            median(monthly_totals),
            "estimate",
            [money(min(monthly_totals)), money(max(monthly_totals))],
            "established",
        )
    if recurring_type != "Fixed recurring":
        if any(len(by_month[month]) > 1 for month in recent_months):
            return None, "unknown", None, None
        recent = [by_month[month][0].amount for month in recent_months]
        if len(recent) < 3:
            return None, "unknown", None, None
        typical = median(recent)
        reliable = sum(_within_fixed_band(value, typical) for value in recent)
        required = len(recent) if len(recent) <= 4 else len(recent) - 1
        if reliable < required:
            return None, "unknown", None, None
        return typical, "estimate", None, "established"
    if len(recent_months) == 1 and len(by_month[recent_months[0]]) == 1:
        return recent_charges[0].amount, "estimate", None, "provisional"
    if len(recent_months) == 2 and all(len(by_month[month]) == 1 for month in recent_months):
        recent = [by_month[month][0].amount for month in recent_months]
        if _directly_similar_fixed_amounts(recent[0], recent[1]):
            return median(recent), "estimate", None, "developing"
        return None, "unknown", None, None
    component = _stable_fixed_component(by_month, recent_months)
    if component is None:
        return None, "unknown", None, None
    return median([item.amount for item in component]), "estimate", None, "established"


def _projected_occurrence(
    *, series_id: str, month: str, display_name: str,
    payment_type: str, card: str, amount: Decimal | None, amount_evidence: str,
    recent_range: list[float] | None, amount_confidence: str | None,
    expected_date: str | None, annual: bool,
) -> InternalOccurrence:
    return {
        "occurrence_id": recurring_occurrence_identity(series_id, month),
        "expected_date": expected_date,
        "date_evidence": "estimated" if expected_date else "month_only",
        "display_name": display_name,
        "card": card_dict(card),
        "payment_type": payment_type,
        "amount": money(amount) if amount is not None else None,
        "amount_evidence": amount_evidence,
        "amount_confidence": amount_confidence,
        "occurrence_status": "expected",
        "recent_range": recent_range,
        "installment_number": None,
        "installment_total": None,
        "annual": annual,
        "ending": False,
        "_month": month,
        "_logical_card": card,
    }



def _unresolved_recurring(
    profile: RecurringForecastEvidence, reason: str, card: str | None,
) -> UnresolvedForecast:
    return {
        "source_kind": "recurring_profile",
        "source_id": profile.profile_id,
        "display_name": profile.display_name,
        "card": card_dict(card) if card else None,
        "reason": reason,
    }


def _reconcile_projected_occurrence(
    profile: RecurringForecastEvidence,
    forecast: InternalOccurrence,
    actuals: Sequence[ChargeEvidence],
) -> list[InternalOccurrence]:
    """Reconcile one logical-card projection with its assigned actual rows."""
    if not actuals:
        return [forecast]
    matched = (
        actuals[0] if len(actuals) == 1 else
        _matching_actual(actuals, forecast["amount"], forecast["expected_date"])
        if profile.recurring_type == "Fixed recurring" else None
    )
    result: list[InternalOccurrence] = []
    if matched is not None:
        result.append(actual_occurrence(
            matched,
            occurrence_id=forecast["occurrence_id"],
            display_name=profile.display_name,
            payment_type=profile.recurring_type,
            status="confirmed",
            annual=forecast["annual"],
        ))
    result.extend(
        actual_occurrence(
            actual,
            occurrence_id=unexpected_actual_identity(actual.transaction_key),
            display_name=profile.display_name,
            payment_type=profile.recurring_type,
            status="unexpected_actual",
            annual=forecast["annual"],
        )
        for actual in actuals if actual is not matched
    )
    return result



def recurring_occurrences(
    profile: RecurringForecastEvidence, anchor_month: str, horizon_end: str,
) -> tuple[list[InternalOccurrence], list[UnresolvedForecast]]:
    baseline_start = shift_month(anchor_month, -24)
    baseline = sorted(
        (item for item in profile.charges if baseline_start <= item.report_month < anchor_month),
        key=lambda item: (item.report_month, item.transaction_key),
    )
    horizon = sorted(
        (item for item in profile.charges if anchor_month <= item.report_month <= horizon_end),
        key=lambda item: (item.report_month, item.transaction_key),
    )
    cadence = canonical_cadence(profile.cadence)
    cadence_months = CADENCE_MONTHS.get(cadence, 0)
    lifecycle = profile.lifecycle_status or "unknown"
    reviewed_monthly = (
        lifecycle == "active"
        and cadence_months == 1
        and profile.recurring_type == "Fixed recurring"
    )
    anchor_evidence = [
        item for item in horizon if item.report_month == anchor_month
    ]
    schedule_evidence = (
        baseline if baseline or not reviewed_monthly else anchor_evidence
    )
    unresolved: list[UnresolvedForecast] = []
    slots: dict[str, list[ChargeEvidence]] | None = None
    phase: int | None = None
    expected_months: list[str] = []
    evidence_card = single_evidence_card([*baseline, *horizon])
    inactive = lifecycle == "paused" or (
        lifecycle == "ended"
        and profile.end_month is not None
        and profile.end_month < anchor_month
    )
    if lifecycle not in {"active", "ended", "paused"} or (
        lifecycle == "ended" and not profile.end_month
    ):
        unresolved.append(_unresolved_recurring(
            profile, "unknown_lifecycle", evidence_card,
        ))
    elif not inactive:
        phase, reason = _schedule_phase(
            schedule_evidence, cadence_months, reviewed_monthly=reviewed_monthly,
        )
        if reason:
            unresolved.append(_unresolved_recurring(profile, reason, evidence_card))
        elif phase is not None:
            expected_months = [
                month for month in (
                    shift_month(anchor_month, offset) for offset in range(3)
                )
                if month_number(month) % cadence_months == phase
                and not (
                    lifecycle == "ended"
                    and profile.end_month
                    and month > profile.end_month
                )
            ]
            if expected_months:
                slots, card_reason = _resolve_card_slots(
                    schedule_evidence, phase, cadence_months,
                )
                if card_reason:
                    unresolved.append(_unresolved_recurring(
                        profile, card_reason, evidence_card,
                    ))

    projected: list[InternalOccurrence] = []
    projection_allowed = not inactive and lifecycle in {"active", "ended"} and not unresolved
    if projection_allowed and slots and phase is not None:
        for card, card_charges in slots.items():
            series_id = recurring_series_identity(profile.profile_id, card)
            amount_charges = list(card_charges)
            amount, amount_evidence, recent_range, amount_confidence = _amount_projection(
                profile.recurring_type, card_charges,
            )
            if reviewed_monthly and amount_confidence != "established":
                anchor_card_charges = [
                    item for item in anchor_evidence if item.card == card
                ]
                selected_anchor = _matching_actual(
                    anchor_card_charges,
                    amount,
                    estimated_date(card_charges, anchor_month),
                )
                if selected_anchor is not None and selected_anchor not in amount_charges:
                    amount_charges.append(selected_anchor)
                    amount, amount_evidence, recent_range, amount_confidence = (
                        _amount_projection(profile.recurring_type, amount_charges)
                    )
            for month in expected_months:
                projected.append(_projected_occurrence(
                    series_id=series_id,
                    month=month,
                    display_name=profile.display_name,
                    payment_type=profile.recurring_type,
                    card=card,
                    amount=amount,
                    amount_evidence=amount_evidence,
                    recent_range=recent_range,
                    amount_confidence=amount_confidence,
                    expected_date=estimated_date(amount_charges, month),
                    annual=cadence_months == 12,
                ))

    by_month: dict[str, list[ChargeEvidence]] = defaultdict(list)
    for charge in horizon:
        by_month[charge.report_month].append(charge)
    output: list[InternalOccurrence] = []
    projected_by_month: dict[str, list[InternalOccurrence]] = defaultdict(list)
    for item in projected:
        projected_by_month[item["_month"]].append(item)
    for month in (shift_month(anchor_month, offset) for offset in range(3)):
        actuals = by_month.get(month, [])
        forecasts = projected_by_month.get(month, [])
        if not actuals:
            output.extend(forecasts)
            continue
        if len(actuals) == 1 and len(forecasts) == 1:
            actual = actuals[0]
            forecast = forecasts[0]
            if actual.card == forecast["_logical_card"]:
                output.extend(_reconcile_projected_occurrence(
                    profile, forecast, [actual],
                ))
            else:
                output.append(actual_occurrence(
                    actual,
                    occurrence_id=forecast["occurrence_id"],
                    display_name=profile.display_name,
                    payment_type=profile.recurring_type,
                    status="unexpected_card",
                    annual=forecast["annual"],
                ))
            continue
        if len(forecasts) == 1:
            forecast = forecasts[0]
            same_card = [
                actual for actual in actuals
                if actual.card == forecast["_logical_card"]
            ]
            if same_card:
                output.extend(_reconcile_projected_occurrence(
                    profile, forecast, same_card,
                ))
            for actual in actuals:
                if actual in same_card:
                    continue
                output.append(actual_occurrence(
                    actual,
                    occurrence_id=unexpected_actual_identity(actual.transaction_key),
                    display_name=profile.display_name,
                    payment_type=profile.recurring_type,
                    status="unexpected_actual",
                    annual=forecast["annual"],
                ))
            continue
        if len(forecasts) > 1:
            actuals_by_card: dict[str, list[ChargeEvidence]] = defaultdict(list)
            for actual in actuals:
                actuals_by_card[actual.card].append(actual)
            forecast_cards = {item["_logical_card"] for item in forecasts}
            for forecast in forecasts:
                matches = actuals_by_card.get(forecast["_logical_card"], [])
                output.extend(_reconcile_projected_occurrence(
                    profile, forecast, matches,
                ))
            for card, unmatched in actuals_by_card.items():
                if card in forecast_cards:
                    continue
                for actual in unmatched:
                    output.append(actual_occurrence(
                        actual,
                        occurrence_id=unexpected_actual_identity(actual.transaction_key),
                        display_name=profile.display_name,
                        payment_type=profile.recurring_type,
                        status="unexpected_actual",
                        annual=cadence_months == 12,
                    ))
            continue
        for actual in actuals:
            output.append(actual_occurrence(
                actual,
                occurrence_id=unexpected_actual_identity(actual.transaction_key),
                display_name=profile.display_name,
                payment_type=profile.recurring_type,
                status="unexpected_actual",
                annual=cadence_months == 12,
            ))
    return output, unresolved
