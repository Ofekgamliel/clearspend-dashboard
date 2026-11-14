from __future__ import annotations

import unittest

from clearspend.observations.grouping import (
    ObservationFinding,
    active_observation_findings,
    assemble_active_observation_groups,
    group_observation_findings,
)


def finding(
    observation_type: str,
    label: str,
    *,
    score: float = 0,
    entity_label: str = "",
    habit_kind: str = "",
    result: str = "Result",
    card_summary: str | None = None,
    finding_key: str = "",
) -> ObservationFinding:
    return ObservationFinding(
        observation_type=observation_type,
        label=label,
        title=f"Title for {label}",
        description=f"Description for {label}",
        score=score,
        entity_label=entity_label,
        habit_kind=habit_kind,
        value=f"Value for {label}",
        comparison=f"Comparison for {label}",
        result=result,
        card_summary=card_summary,
        finding_key=finding_key,
    )


class ObservationGroupingTests(unittest.TestCase):
    def test_single_finding_preserves_content_and_uses_value_as_default_summary(self) -> None:
        group = group_observation_findings([
            finding("LARGE PURCHASE", "Synthetic merchant"),
        ])[0]
        self.assertEqual(group.title, "Title for Synthetic merchant")
        self.assertEqual(group.description, "Description for Synthetic merchant")
        self.assertEqual(group.card_summary, "Value for Synthetic merchant")
        self.assertEqual(len(group.items), 1)

    def test_explicit_empty_single_card_summary_is_preserved(self) -> None:
        group = group_observation_findings([
            finding("LARGE PURCHASE", "Synthetic merchant", card_summary=""),
        ])[0]
        self.assertEqual(group.card_summary, "")

    def test_generic_group_orders_by_score_and_summarizes_repeated_entities(self) -> None:
        group = group_observation_findings([
            finding("RECURRING AMOUNT INCREASED", "Alias one", score=1, entity_label="Service"),
            finding("RECURRING AMOUNT INCREASED", "Alias two", score=3, entity_label="Service"),
        ])[0]
        self.assertEqual(group.items[0].label, "Alias two")
        self.assertEqual(group.title, "2 recurring amount increases")
        self.assertEqual(group.merchant_preview, "Service")
        self.assertEqual(group.card_summary, "2 findings for 1 merchant")

    def test_preview_shows_two_entities_and_remaining_count(self) -> None:
        group = group_observation_findings([
            finding("LARGE PURCHASE", "One", score=3),
            finding("LARGE PURCHASE", "Two", score=2),
            finding("LARGE PURCHASE", "Three", score=1),
        ])[0]
        self.assertEqual(group.merchant_preview, "One · Two · +1 more")
        self.assertEqual(group.card_summary, "")

    def test_category_increase_group_uses_two_compact_rows(self) -> None:
        group = group_observation_findings([
            finding("CATEGORY SPENDING INCREASED", "Food", score=1, result="+₪1"),
            finding("CATEGORY SPENDING INCREASED", "Travel", score=3, result="+₪3"),
            finding("CATEGORY SPENDING INCREASED", "Fashion", score=2, result="+₪2"),
        ])[0]
        self.assertEqual(group.title, "3 categories increased significantly")
        self.assertEqual(
            tuple((item.label, item.result) for item in group.compact_categories),
            (("Travel", "+₪3"), ("Fashion", "+₪2")),
        )
        self.assertEqual(group.card_summary, "+1 more categories")
        self.assertEqual(group.primary_label, "Open category activity →")

    def test_all_regular_merchant_group_uses_entity_preview(self) -> None:
        group = group_observation_findings([
            finding("MERCHANT HABIT SHIFTED", "One", habit_kind="Merchant became regular"),
            finding("MERCHANT HABIT SHIFTED", "Two", habit_kind="Merchant became regular"),
        ])[0]
        self.assertEqual(group.title, "2 merchants became regular")
        self.assertEqual(group.merchant_preview, "One · Two")
        self.assertEqual(group.comparison, "2 merchants")

    def test_mixed_merchant_group_uses_subtype_summary(self) -> None:
        group = group_observation_findings([
            finding("MERCHANT HABIT SHIFTED", "One", habit_kind="Merchant became regular"),
            finding("MERCHANT HABIT SHIFTED", "Two", habit_kind="Buying more often"),
            finding(
                "MERCHANT HABIT SHIFTED",
                "Three",
                habit_kind="Typical purchase amount decreased",
            ),
        ])[0]
        self.assertEqual(group.title, "3 merchant habit shifts")
        self.assertEqual(
            group.merchant_preview,
            "1 became regular · 1 buying more often · 1 purchase-amount change",
        )

    def test_groups_follow_established_type_priority(self) -> None:
        groups = group_observation_findings([
            finding("UNUSUAL TRANSACTION", "Unusual"),
            finding("CATEGORY SPENDING INCREASED", "Category"),
            finding("POSSIBLE DUPLICATE", "Duplicate"),
            finding("AMOUNT LEFT DECREASED", "Income"),
        ])
        self.assertEqual(tuple(group.observation_type for group in groups), (
            "AMOUNT LEFT DECREASED",
            "POSSIBLE DUPLICATE",
            "CATEGORY SPENDING INCREASED",
            "UNUSUAL TRANSACTION",
        ))

    def test_reviewed_keyed_findings_are_suppressed_but_facts_remain(self) -> None:
        duplicate = finding(
            "POSSIBLE DUPLICATE",
            "Duplicate",
            finding_key="POSSIBLE DUPLICATE:1,2",
        )
        factual = finding("LARGE PURCHASE", "Large")
        active = active_observation_findings(
            (duplicate, factual), ("POSSIBLE DUPLICATE:1,2",),
        )
        self.assertEqual(active, (factual,))

    def test_unrelated_review_key_does_not_hide_a_finding(self) -> None:
        unusual = finding(
            "UNUSUAL TRANSACTION",
            "Unusual",
            finding_key="UNUSUAL TRANSACTION:7",
        )
        self.assertEqual(active_observation_findings(
            (unusual,), ("UNUSUAL TRANSACTION:8",),
        ), (unusual,))

    def test_groups_are_rebuilt_after_one_grouped_finding_is_reviewed(self) -> None:
        first = finding(
            "POSSIBLE DUPLICATE",
            "First",
            score=20,
            finding_key="POSSIBLE DUPLICATE:1,2",
        )
        second = finding(
            "POSSIBLE DUPLICATE",
            "Second",
            score=10,
            finding_key="POSSIBLE DUPLICATE:3,4",
        )
        groups = assemble_active_observation_groups(
            (first, second), (first.finding_key,),
        )
        self.assertEqual(len(groups), 1)
        self.assertEqual(groups[0].items, (second,))
        self.assertEqual(groups[0].title, "Title for Second")

    def test_group_disappears_when_all_its_findings_are_reviewed(self) -> None:
        duplicate = finding(
            "POSSIBLE DUPLICATE",
            "Duplicate",
            finding_key="POSSIBLE DUPLICATE:1,2",
        )
        self.assertEqual(assemble_active_observation_groups(
            (duplicate,), (duplicate.finding_key,),
        ), ())


if __name__ == "__main__":
    unittest.main()
