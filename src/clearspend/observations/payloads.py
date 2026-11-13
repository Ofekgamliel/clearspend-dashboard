"""JSON-ready compatibility serialization for backend-owned observations."""

from __future__ import annotations

from pathlib import Path

from clearspend.observations.grouping import ObservationFinding, ObservationGroup
from clearspend.observations.read_service import ObservationView


def finding_payload(finding: ObservationFinding) -> dict:
    """Serialize one finding using the established browser field names."""
    payload = {
        "type": finding.observation_type,
        "month": finding.month,
        "label": finding.label,
        "title": finding.title,
        "description": finding.description,
        "score": finding.score,
        "value": finding.value,
        "comparison": finding.comparison,
        "result": finding.result,
        "evidence": list(finding.evidence),
    }
    optional = {
        "entityLabel": finding.entity_label,
        "entitySublabel": finding.entity_sublabel,
        "patternPeriod": finding.pattern_period,
        "habitKind": finding.habit_kind,
        "valueLabel": finding.value_label,
        "comparisonLabel": finding.comparison_label,
        "comparisonDetail": finding.comparison_detail,
        "resultLabel": finding.result_label,
        "ruleText": finding.rule_text,
        "findingKey": finding.finding_key,
        "primaryLabel": finding.primary_label,
        "recurringSeriesId": finding.recurring_series_id,
        "occurrenceStart": finding.occurrence_start,
        "occurrenceEnd": finding.occurrence_end,
    }
    payload.update({key: value for key, value in optional.items() if value})
    if finding.event_label is not None:
        payload["eventLabel"] = finding.event_label
    if finding.card_summary is not None:
        payload["cardSummary"] = finding.card_summary
    if finding.transaction_ids:
        payload["transactionIds"] = list(finding.transaction_ids)
    if finding.card_comparison_primary or finding.card_comparison_secondary:
        payload["cardComparison"] = {
            "primary": finding.card_comparison_primary,
            "secondary": finding.card_comparison_secondary,
        }
    return payload


def group_payload(group: ObservationGroup) -> dict:
    """Serialize one grouped card without moving visual styling to the backend."""
    payload = {
        "type": group.observation_type,
        "items": [finding_payload(item) for item in group.items],
        "title": group.title,
        "description": group.description,
        "value": group.value,
        "comparison": group.comparison,
        "result": group.result,
        "cardSummary": group.card_summary,
        "singular": group.singular,
        "entities": group.entities,
    }
    optional = {
        "merchantPreview": group.merchant_preview,
        "primaryLabel": group.primary_label,
    }
    payload.update({key: value for key, value in optional.items() if value})
    if group.compact_categories:
        payload["compactCategories"] = [
            {"label": item.label, "result": item.result}
            for item in group.compact_categories
        ]
    if group.card_comparison_primary or group.card_comparison_secondary:
        payload["cardComparison"] = {
            "primary": group.card_comparison_primary,
            "secondary": group.card_comparison_secondary,
        }
    return payload


def observation_view_payload(view: ObservationView) -> dict:
    """Serialize an analyzed view as the future observation API contract."""
    return {
        "period": view.period,
        "selectedCard": view.selected_card,
        "selectedMonth": view.selected_month,
        "observedStart": view.observed_start,
        "observedEnd": view.observed_end,
        "historical": view.historical,
        "findingCount": view.finding_count,
        "typeCount": view.type_count,
        "findings": [finding_payload(item) for item in view.findings],
        "groups": [group_payload(item) for item in view.groups],
    }


def observations_payload(
    database: Path,
    *,
    period: str,
    card: str,
    month: str = "",
    income_hidden: bool = False,
) -> dict:
    """Build the read-only payload consumed by the observations API route."""
    from clearspend.observations.read_service import load_observation_view

    return observation_view_payload(load_observation_view(
        database,
        period=period,
        card=card,
        month=month,
        income_hidden=income_hidden,
    ))
