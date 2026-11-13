"""Framework-independent grouping for qualified financial observations."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable


@dataclass(frozen=True)
class ObservationTypeMeta:
    priority: int
    plural: str
    singular: str = "merchant"
    entities: str = "merchants"


OBSERVATION_TYPE_META: dict[str, ObservationTypeMeta] = {
    "AMOUNT LEFT TREND": ObservationTypeMeta(1, "amount-left trends", "period", "periods"),
    "SPENDING ROUTINE SHIFTED": ObservationTypeMeta(2, "spending routine shifts", "period", "periods"),
    "RECURRING BURDEN SHIFTED": ObservationTypeMeta(3, "recurring burden shifts", "period", "periods"),
    "PERSISTENT INSTALLMENT BURDEN": ObservationTypeMeta(4, "persistent installment patterns", "period", "periods"),
    "CATEGORY ROUTINE SHIFTED": ObservationTypeMeta(5, "category routine shifts", "category", "categories"),
    "MERCHANT HABIT SHIFTED": ObservationTypeMeta(6, "merchant habit shifts"),
    "AMOUNT LEFT DECREASED": ObservationTypeMeta(1, "periods with less income remaining", "period", "periods"),
    "POSSIBLE DUPLICATE": ObservationTypeMeta(2, "possible duplicate groups"),
    "ADDITIONAL RECURRING CHARGE": ObservationTypeMeta(3, "additional recurring-charge findings"),
    "RECURRING AMOUNT INCREASED": ObservationTypeMeta(4, "recurring amount increases"),
    "FEE AMOUNT INCREASED": ObservationTypeMeta(5, "fee amount increases"),
    "FIRST FEE OBSERVED": ObservationTypeMeta(6, "first-observed fees"),
    "CATEGORY SPENDING INCREASED": ObservationTypeMeta(7, "category spending increases", "category", "categories"),
    "MERCHANT ACTIVITY CHANGED": ObservationTypeMeta(8, "merchant activity changes"),
    "LARGE AND UNUSUAL PURCHASE": ObservationTypeMeta(9, "large and unusual purchases"),
    "LARGE PURCHASE": ObservationTypeMeta(10, "large purchases"),
    "UNUSUAL TRANSACTION": ObservationTypeMeta(11, "unusual transactions"),
}


@dataclass(frozen=True)
class ObservationFinding:
    observation_type: str
    label: str
    title: str
    description: str
    score: float = 0.0
    entity_label: str = ""
    habit_kind: str = ""
    value: str = ""
    comparison: str = ""
    result: str = ""
    card_summary: str | None = None
    finding_key: str = ""
    month: str = ""
    entity_sublabel: str = ""
    pattern_period: str = ""
    value_label: str = ""
    comparison_label: str = ""
    comparison_detail: str = ""
    result_label: str = ""
    rule_text: str = ""
    evidence: tuple[str, ...] = ()
    card_comparison_primary: str = ""
    card_comparison_secondary: str = ""
    primary_label: str = ""
    transaction_ids: tuple[int, ...] = ()
    recurring_series_id: str = ""
    occurrence_start: str = ""
    occurrence_end: str = ""
    event_label: str | None = None

    @property
    def entity(self) -> str:
        return self.entity_label or self.label


@dataclass(frozen=True)
class CompactCategoryFinding:
    label: str
    result: str


@dataclass(frozen=True)
class ObservationGroup:
    observation_type: str
    items: tuple[ObservationFinding, ...]
    title: str
    description: str
    value: str
    comparison: str
    result: str
    merchant_preview: str = ""
    card_summary: str = ""
    compact_categories: tuple[CompactCategoryFinding, ...] = ()
    primary_label: str = ""
    singular: str = "merchant"
    entities: str = "merchants"
    card_comparison_primary: str = ""
    card_comparison_secondary: str = ""


def _unique_entities(items: Iterable[ObservationFinding]) -> tuple[str, ...]:
    return tuple(dict.fromkeys(item.entity for item in items))


def group_observation_findings(
    findings: Iterable[ObservationFinding],
) -> tuple[ObservationGroup, ...]:
    """Group findings into the established dashboard-card structure."""
    grouped: dict[str, list[ObservationFinding]] = {}
    for finding in findings:
        grouped.setdefault(finding.observation_type, []).append(finding)

    result: list[ObservationGroup] = []
    for observation_type, raw_items in grouped.items():
        items = tuple(sorted(raw_items, key=lambda item: -item.score))
        top = items[0]
        type_meta = OBSERVATION_TYPE_META.get(
            observation_type, ObservationTypeMeta(99, "findings"),
        )
        if len(items) == 1:
            result.append(ObservationGroup(
                observation_type=observation_type,
                items=items,
                title=top.title,
                description=top.description,
                value=top.value,
                comparison=top.comparison,
                result=top.result,
                card_summary=top.value if top.card_summary is None else top.card_summary,
                primary_label=top.primary_label,
                singular=type_meta.singular,
                entities=type_meta.entities,
                card_comparison_primary=top.card_comparison_primary,
                card_comparison_secondary=top.card_comparison_secondary,
            ))
            continue

        names = _unique_entities(items)
        preview = " · ".join(names[:2])
        if len(names) > 2:
            preview += f" · +{len(names) - 2} more"
        repeated_entity_summary = (
            f"{len(items)} findings for {len(names)} "
            f"{type_meta.singular if len(names) == 1 else type_meta.entities}"
            if len(items) != len(names)
            else ""
        )

        if observation_type == "CATEGORY SPENDING INCREASED":
            compact = tuple(
                CompactCategoryFinding(item.label, item.result) for item in items[:2]
            )
            result.append(ObservationGroup(
                observation_type=observation_type,
                items=items,
                title=f"{len(items)} categories increased significantly",
                description="Compared with each category’s previous three-month median.",
                value="",
                comparison="",
                result="",
                card_summary=(
                    f"+{len(items) - 2} more categories" if len(items) > 2 else ""
                ),
                compact_categories=compact,
                primary_label="Open category activity →",
                singular=type_meta.singular,
                entities=type_meta.entities,
            ))
            continue

        if observation_type == "MERCHANT HABIT SHIFTED":
            kinds = tuple(item.habit_kind for item in items)
            regular = kinds.count("Merchant became regular")
            buying_more = kinds.count("Buying more often")
            buying_less = kinds.count("Buying less often")
            amount_changes = sum(
                kind.startswith("Typical purchase amount") for kind in kinds
            )
            all_regular = regular == len(items)
            subtype_summary = " · ".join(
                value for value in (
                    f"{regular} became regular" if regular else "",
                    f"{buying_more} buying more often" if buying_more else "",
                    f"{buying_less} buying less often" if buying_less else "",
                    (
                        f"{amount_changes} purchase-amount "
                        f"{'change' if amount_changes == 1 else 'changes'}"
                        if amount_changes else ""
                    ),
                ) if value
            )
            result.append(ObservationGroup(
                observation_type=observation_type,
                items=items,
                title=(
                    f"{len(items)} merchants became regular"
                    if all_regular else f"{len(items)} merchant habit shifts"
                ),
                description=(
                    "These merchants established repeated purchase activity during the selected history."
                    if all_regular
                    else "This card combines established habits with later frequency and typical-purchase changes."
                ),
                value=f"{len(items)} findings",
                comparison=f"{len(names)} merchants",
                result=f"{len(items)} patterns",
                merchant_preview=preview if all_regular else subtype_summary,
                primary_label="Open merchant activity →",
                singular=type_meta.singular,
                entities=type_meta.entities,
            ))
            continue

        result.append(ObservationGroup(
            observation_type=observation_type,
            items=items,
            title=f"{len(items)} {type_meta.plural}",
            description=(
                "Each finding keeps its own observed value, exact comparison basis, and result."
            ),
            value=f"{len(items)} findings",
            comparison="Multiple matching observations",
            result=f"{len(items)} items",
            merchant_preview=preview,
            card_summary=repeated_entity_summary,
            primary_label="Open related activity →",
            singular=type_meta.singular,
            entities=type_meta.entities,
        ))

    return tuple(sorted(
        result,
        key=lambda group: OBSERVATION_TYPE_META.get(
            group.observation_type, ObservationTypeMeta(99, "findings"),
        ).priority,
    ))


def active_observation_findings(
    findings: Iterable[ObservationFinding],
    reviewed_finding_keys: Iterable[str],
) -> tuple[ObservationFinding, ...]:
    """Suppress only keyed findings with an active persisted review decision."""
    reviewed = set(reviewed_finding_keys)
    return tuple(
        finding
        for finding in findings
        if not finding.finding_key or finding.finding_key not in reviewed
    )


def assemble_active_observation_groups(
    findings: Iterable[ObservationFinding],
    reviewed_finding_keys: Iterable[str],
) -> tuple[ObservationGroup, ...]:
    """Apply reversible review state before card grouping and ordering."""
    return group_observation_findings(
        active_observation_findings(findings, reviewed_finding_keys),
    )
