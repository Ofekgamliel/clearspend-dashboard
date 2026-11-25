from __future__ import annotations

import unittest
from decimal import Decimal

from clearspend.recurring.forecast import (
    ChargeEvidence,
    InstallmentForecastEvidence,
    RecurringForecastEvidence,
    build_upcoming_forecast,
)


def charge(
    key: str,
    month: str,
    amount: str = "100",
    *,
    last4: str = "0001",
    day: int = 10,
    transaction_date: str | None = None,
    billing_date: str | None = None,
    currency: str = "ILS",
    installment_number: int | None = None,
    installment_total: int | None = None,
) -> ChargeEvidence:
    return ChargeEvidence(
        transaction_key=key,
        report_month=month,
        amount=Decimal(amount),
        provider="synthetic",
        card_last4=last4,
        transaction_date=transaction_date or f"{month}-{day:02d}",
        billing_date=billing_date,
        charged_currency=currency,
        installment_number=installment_number,
        installment_total=installment_total,
    )


def profile(
    charges: list[ChargeEvidence],
    *,
    profile_id: str = "synthetic-service",
    display_name: str = "Synthetic Service",
    cadence: str = "Monthly",
    recurring_type: str = "Fixed recurring",
    lifecycle: str = "active",
    end_month: str | None = None,
) -> RecurringForecastEvidence:
    return RecurringForecastEvidence(
        profile_id=profile_id,
        display_name=display_name,
        recurring_type=recurring_type,
        cadence=cadence,
        lifecycle_status=lifecycle,
        end_month=end_month,
        charges=tuple(charges),
    )


class RecurringForecastTests(unittest.TestCase):
    def forecast(
        self,
        profiles: list[RecurringForecastEvidence] | None = None,
        plans: list[InstallmentForecastEvidence] | None = None,
        card_scope: str = "all",
    ) -> dict:
        return build_upcoming_forecast(
            profiles or [],
            plans or [],
            anchor_month="2030-04",
            generated_as_of="2030-04-02T10:00:00+03:00",
            selected_card=card_scope,
        )

    def test_fixed_monthly_projection_uses_bounded_amount_and_date_evidence(self) -> None:
        evidence = profile([
            charge("jan", "2030-01", "100", day=9),
            charge("feb", "2030-02", "105", day=10),
            charge("mar", "2030-03", "100", day=11),
        ])

        result = self.forecast([evidence])

        self.assertEqual([item["payment_count"] for item in result["months"]], [1, 1, 1])
        payment = result["months"][0]["payments"][0]
        self.assertEqual(payment["amount"], 100)
        self.assertEqual(payment["amount_evidence"], "estimate")
        self.assertEqual(payment["amount_confidence"], "established")
        self.assertEqual(payment["expected_date"], "2030-04-10")
        self.assertEqual(payment["date_evidence"], "estimated")
        self.assertNotIn("category", payment)

    def test_unique_actual_replaces_projection_and_keeps_opaque_occurrence_id(self) -> None:
        evidence = profile([
            charge("jan", "2030-01"),
            charge("feb", "2030-02"),
            charge("mar", "2030-03"),
            charge("private-transaction-key", "2030-04", "110"),
        ])

        result = self.forecast([evidence])
        payment = result["months"][0]["payments"][0]

        self.assertEqual(payment["occurrence_status"], "confirmed")
        self.assertEqual(payment["amount_evidence"], "confirmed")
        self.assertNotIn("category", payment)
        self.assertNotIn("private-transaction-key", payment["occurrence_id"])
        self.assertNotIn("transaction_key", payment)
        self.assertEqual(result["months"][0]["forecast_total"], 0)
        self.assertEqual(result["months"][0]["confirmed_total"], 110)

    def test_established_anchor_match_survives_a_clearly_different_extra(self) -> None:
        evidence = profile([
            charge("jan", "2030-01"),
            charge("feb", "2030-02"),
            charge("mar", "2030-03"),
            charge("apr-a", "2030-04", "100"),
            charge("apr-b", "2030-04", "25"),
        ])

        result = self.forecast([evidence])
        april = result["months"][0]

        self.assertEqual(april["payment_count"], 2)
        self.assertEqual(april["confirmed_total"], 125)
        self.assertEqual(april["forecast_total"], 0)
        self.assertEqual(
            {item["occurrence_status"] for item in april["payments"]},
            {"confirmed", "unexpected_actual"},
        )
        matched = next(item for item in april["payments"] if item["amount"] == 100)
        extra = next(item for item in april["payments"] if item["amount"] == 25)
        self.assertEqual(matched["occurrence_status"], "confirmed")
        self.assertEqual(extra["occurrence_status"], "unexpected_actual")
        self.assertEqual(result["months"][1]["payments"][0]["amount"], 100)
        self.assertEqual(
            result["months"][1]["payments"][0]["amount_confidence"],
            "established",
        )

    def test_anchor_timing_distinguishes_a_similarly_sized_extra(self) -> None:
        evidence = profile([
            charge("jan", "2030-01", "100", day=10),
            charge("feb", "2030-02", "100", day=10),
            charge("mar", "2030-03", "100", day=10),
            charge("apr-normal", "2030-04", "100", day=10),
            charge("apr-extra", "2030-04", "105", day=20),
        ])

        result = self.forecast([evidence])
        april = result["months"][0]

        normal = next(item for item in april["payments"] if item["amount"] == 100)
        extra = next(item for item in april["payments"] if item["amount"] == 105)
        self.assertEqual(normal["occurrence_status"], "confirmed")
        self.assertEqual(extra["occurrence_status"], "unexpected_actual")
        self.assertEqual(result["months"][1]["payments"][0]["amount"], 100)

    def test_equally_plausible_anchor_matches_stay_ambiguous_without_erasing_future(self) -> None:
        evidence = profile([
            charge("jan", "2030-01", "100", day=10),
            charge("feb", "2030-02", "100", day=10),
            charge("mar", "2030-03", "100", day=10),
            charge("apr-a", "2030-04", "100", day=10),
            charge("apr-b", "2030-04", "105", day=10),
        ])

        result = self.forecast([evidence])

        self.assertEqual(
            {item["occurrence_status"] for item in result["months"][0]["payments"]},
            {"unexpected_actual"},
        )
        for month in result["months"][1:]:
            payment = month["payments"][0]
            self.assertEqual(payment["amount"], 100)
            self.assertEqual(payment["amount_confidence"], "established")

    def test_unresolved_schedule_keeps_actual_charge_outside_projected_totals(self) -> None:
        evidence = profile([
            charge("baseline", "2030-03"),
            charge("actual", "2030-04", "90"),
        ], cadence="Custom")

        result = self.forecast([evidence])

        self.assertEqual(result["unresolved"][0]["reason"], "unsupported_cadence")
        self.assertEqual(result["months"][0]["payment_count"], 1)
        self.assertEqual(result["months"][0]["confirmed_total"], 90)
        self.assertEqual(
            result["months"][0]["payments"][0]["occurrence_status"],
            "unexpected_actual",
        )

    def test_parallel_cards_remain_distinct_and_card_scope_filters_output(self) -> None:
        charges = []
        for month in ("2030-01", "2030-02", "2030-03"):
            charges.extend([
                charge(f"a-{month}", month, "40", last4="0001"),
                charge(f"b-{month}", month, "60", last4="0002"),
            ])
        evidence = profile(charges)

        all_cards = self.forecast([evidence])
        one_card = self.forecast([evidence], card_scope="synthetic:0001")

        self.assertEqual(all_cards["months"][0]["payment_count"], 2)
        self.assertEqual(one_card["months"][0]["payment_count"], 1)
        self.assertEqual(one_card["months"][0]["forecast_total"], 40)

    def test_parallel_cards_reconcile_matching_actuals_and_keep_one_extra(self) -> None:
        charges = []
        for month in ("2030-01", "2030-02", "2030-03"):
            charges.extend([
                charge(f"a-{month}", month, "40", last4="0001"),
                charge(f"b-{month}", month, "60", last4="0002"),
            ])
        charges.extend([
            charge("a-match", "2030-04", "40", last4="0001"),
            charge("a-extra", "2030-04", "10", last4="0001"),
            charge("b-match", "2030-04", "60", last4="0002"),
        ])
        evidence = profile(charges)

        first = self.forecast([evidence])
        second = self.forecast([evidence])
        april = first["months"][0]

        self.assertEqual(april["confirmed_total"], 110)
        self.assertEqual(april["payment_count"], 3)
        self.assertEqual(
            sorted(item["occurrence_status"] for item in april["payments"]),
            ["confirmed", "confirmed", "unexpected_actual"],
        )
        self.assertEqual(first["months"][1]["forecast_total"], 100)
        self.assertEqual(first["months"][2]["forecast_total"], 100)
        self.assertEqual(
            [item["occurrence_id"] for item in april["payments"]],
            [item["occurrence_id"] for item in second["months"][0]["payments"]],
        )

    def test_installments_project_remaining_numbers_and_mark_the_final_payment(self) -> None:
        plan = InstallmentForecastEvidence(
            commitment_id="commitment_synthetic",
            display_name="Synthetic Device",
            charges=(
                charge(
                    "installment-1", "2030-03", "75",
                    installment_number=1, installment_total=3,
                ),
            ),
        )

        result = self.forecast(plans=[plan])
        payments = [
            payment for month in result["months"] for payment in month["payments"]
        ]

        self.assertEqual([item["installment_number"] for item in payments], [2, 3])
        self.assertTrue(payments[-1]["ending"])
        self.assertEqual(payments[-1]["amount"], 75)
        self.assertEqual(payments[-1]["amount_evidence"], "estimate")

    def test_fixed_amount_outside_reliability_boundary_remains_unknown(self) -> None:
        evidence = profile([
            charge("jan", "2030-01", "100"),
            charge("feb", "2030-02", "100"),
            charge("mar", "2030-03", "140"),
        ])

        result = self.forecast([evidence])

        self.assertIsNone(result["months"][0]["payments"][0]["amount"])
        self.assertEqual(result["months"][0]["unknown_amount_count"], 1)
        self.assertEqual(result["months"][0]["comparison_label"], None)

    def test_annual_schedule_appears_only_in_supported_due_month(self) -> None:
        evidence = profile([
            charge("annual-2028", "2028-06", "1200", day=15),
            charge("annual-2029", "2029-06", "1200", day=14),
        ], cadence="Yearly", recurring_type="Scheduled obligation")

        result = self.forecast([evidence])

        self.assertEqual([item["payment_count"] for item in result["months"]], [0, 0, 1])
        payment = result["months"][2]["payments"][0]
        self.assertTrue(payment["annual"])
        self.assertEqual(payment["expected_date"], None)

    def test_ended_and_paused_profiles_withhold_projections_but_keep_actuals(self) -> None:
        baseline = [
            charge("jan", "2030-01"),
            charge("feb", "2030-02"),
            charge("mar", "2030-03"),
        ]
        ended = profile(
            baseline + [charge("ended-actual", "2030-06", "80")],
            lifecycle="ended", end_month="2030-04",
        )
        paused = profile(
            baseline + [charge("paused-actual", "2030-05", "90")],
            lifecycle="paused",
        )

        result = self.forecast([ended, paused])

        self.assertEqual(result["months"][0]["forecast_total"], 100)
        self.assertEqual(result["months"][1]["forecast_total"], 0)
        self.assertEqual(result["months"][1]["confirmed_total"], 90)
        self.assertEqual(result["months"][2]["confirmed_total"], 80)
        self.assertTrue(all(
            payment["occurrence_status"] == "unexpected_actual"
            for month in result["months"][1:]
            for payment in month["payments"]
        ))

    def test_usage_estimate_uses_recent_range_and_clamps_inferred_date(self) -> None:
        evidence = profile([
            charge("jan", "2030-01", "80", day=31),
            charge("feb", "2030-02", "100", day=28),
            charge("mar", "2030-03", "120", day=31),
        ], recurring_type="Usage-based recurring")

        result = self.forecast([evidence])
        april = result["months"][0]["payments"][0]

        self.assertEqual(april["amount"], 100)
        self.assertEqual(april["recent_range"], [80, 120])
        self.assertEqual(april["expected_date"], "2030-04-30")

    def test_matching_horizon_installment_replaces_projection(self) -> None:
        plan = InstallmentForecastEvidence(
            commitment_id="commitment_synthetic",
            display_name="Synthetic Device",
            charges=(
                charge(
                    "installment-1", "2030-03", "75",
                    installment_number=1, installment_total=3,
                ),
                charge(
                    "installment-2", "2030-04", "80",
                    installment_number=2, installment_total=3,
                ),
            ),
        )

        result = self.forecast(plans=[plan])
        april = result["months"][0]

        self.assertEqual(april["payment_count"], 1)
        self.assertEqual(april["confirmed_total"], 80)
        self.assertEqual(april["forecast_total"], 0)
        self.assertEqual(april["payments"][0]["occurrence_status"], "confirmed")
        self.assertEqual(april["payments"][0]["installment_number"], 2)

    def test_unknown_cadence_never_uses_stale_numeric_interval(self) -> None:
        evidence = profile([
            charge("jan", "2030-01"),
            charge("feb", "2030-02"),
            charge("mar", "2030-03"),
        ], cadence="Biweekly")

        result = self.forecast([evidence])

        self.assertEqual(result["unresolved"][0]["reason"], "unsupported_cadence")
        self.assertTrue(all(not month["payments"] for month in result["months"]))

    def test_actual_date_requires_billing_or_same_reporting_month_evidence(self) -> None:
        evidence = profile([
            charge("jan", "2030-01"),
            charge("feb", "2030-02"),
            charge("mar", "2030-03"),
            charge(
                "apr", "2030-04", transaction_date="2030-03-29",
                billing_date="2030-04-07",
            ),
        ])
        billing_date = self.forecast([evidence])["months"][0]["payments"][0]
        purchase_only = profile([
            charge("jan-2", "2030-01"),
            charge("feb-2", "2030-02"),
            charge("mar-2", "2030-03"),
            charge("apr-2", "2030-04", transaction_date="2030-03-29"),
        ])
        month_only = self.forecast([purchase_only])["months"][0]["payments"][0]

        self.assertEqual(billing_date["expected_date"], "2030-04-07")
        self.assertEqual(billing_date["date_evidence"], "confirmed")
        self.assertIsNone(month_only["expected_date"])
        self.assertEqual(month_only["date_evidence"], "month_only")

    def test_shifted_installment_moves_forecast_instead_of_counting_twice(self) -> None:
        plan = InstallmentForecastEvidence(
            commitment_id="commitment_shifted",
            display_name="Synthetic Shifted Device",
            charges=(
                charge(
                    "installment-1", "2030-03", "75",
                    installment_number=1, installment_total=3,
                ),
                charge(
                    "installment-2", "2030-05", "75",
                    installment_number=2, installment_total=3,
                ),
            ),
        )

        result = self.forecast(plans=[plan])
        all_payments = [
            payment for month in result["months"] for payment in month["payments"]
        ]
        second = [item for item in all_payments if item["installment_number"] == 2]

        self.assertEqual(len(second), 1)
        self.assertEqual(second[0]["occurrence_status"], "confirmed")
        self.assertEqual(result["months"][0]["payment_count"], 0)
        self.assertEqual(result["months"][1]["payment_count"], 1)
        self.assertEqual(result["months"][2]["payment_count"], 1)

    def test_card_scope_hides_unresolved_evidence_from_other_cards(self) -> None:
        evidence = profile([
            charge("one", "2030-03", last4="0002"),
        ], cadence="Custom")

        other_card = self.forecast([evidence], card_scope="synthetic:0001")
        matching_card = self.forecast([evidence], card_scope="synthetic:0002")

        self.assertEqual(other_card["unresolved"], [])
        self.assertEqual(len(matching_card["unresolved"]), 1)

    def test_non_ils_and_mixed_currency_amounts_remain_unknown(self) -> None:
        mixed = profile([
            charge("jan", "2030-01", currency="ILS"),
            charge("feb", "2030-02", currency="₪"),
            charge("mar", "2030-03", currency="USD"),
            charge("apr", "2030-04", currency="USD"),
        ])

        result = self.forecast([mixed])
        april = result["months"][0]

        self.assertIsNone(april["payments"][0]["amount"])
        self.assertEqual(april["payments"][0]["amount_evidence"], "unknown")
        self.assertEqual(april["confirmed_total"], 0)
        self.assertEqual(april["unknown_amount_count"], 1)

    def test_obsolete_card_does_not_block_two_current_parallel_cards(self) -> None:
        charges = [charge("old", "2029-12", "25", last4="0003")]
        for month in ("2030-01", "2030-02", "2030-03"):
            charges.extend([
                charge(f"a-{month}", month, "40", last4="0001"),
                charge(f"b-{month}", month, "60", last4="0002"),
            ])

        result = self.forecast([profile(charges)])

        self.assertEqual(result["unresolved"], [])
        self.assertEqual(result["months"][0]["payment_count"], 2)
        self.assertEqual(result["months"][0]["forecast_total"], 100)

    def test_inactive_profiles_skip_schedule_warnings_but_keep_horizon_actuals(self) -> None:
        paused = profile([
            charge("paused-baseline", "2030-03"),
            charge("paused-actual", "2030-04", "90"),
        ], lifecycle="paused")
        ended = profile([
            charge("ended-baseline", "2030-02"),
            charge("ended-actual", "2030-05", "80"),
        ], lifecycle="ended", end_month="2030-03")

        result = self.forecast([paused, ended])
        payments = [
            payment for month in result["months"] for payment in month["payments"]
        ]

        self.assertEqual(result["unresolved"], [])
        self.assertEqual(len(payments), 2)
        self.assertTrue(all(
            item["occurrence_status"] == "unexpected_actual" for item in payments
        ))

    def test_cross_card_unresolved_attribution_uses_baseline_and_horizon(self) -> None:
        moved = profile([
            charge("baseline", "2030-03", last4="0001"),
            charge("actual", "2030-04", last4="0002"),
        ], cadence="Custom")

        all_cards = self.forecast([moved])
        old_card = self.forecast([moved], card_scope="synthetic:0001")
        new_card = self.forecast([moved], card_scope="synthetic:0002")

        self.assertIsNone(all_cards["unresolved"][0]["card"])
        self.assertEqual(old_card["unresolved"], [])
        self.assertEqual(new_card["unresolved"], [])
        self.assertEqual(new_card["months"][0]["payment_count"], 1)
        self.assertEqual(
            new_card["months"][0]["payments"][0]["occurrence_status"],
            "unexpected_actual",
        )

    def test_malformed_horizon_installment_keeps_actual_and_adds_explanation(self) -> None:
        plan = InstallmentForecastEvidence(
            commitment_id="commitment_malformed_horizon",
            display_name="Synthetic Malformed Device",
            charges=(charge(
                "malformed", "2030-04", "75",
                installment_number=None, installment_total=3,
            ),),
        )

        result = self.forecast(plans=[plan])

        self.assertEqual(result["unresolved"][0]["reason"], "invalid_installment_evidence")
        self.assertEqual(result["unresolved"][0]["card"]["last4"], "0001")
        self.assertEqual(result["months"][0]["payment_count"], 1)
        self.assertEqual(
            result["months"][0]["payments"][0]["occurrence_status"],
            "unexpected_actual",
        )

    def test_malformed_horizon_installment_does_not_erase_valid_baseline_projection(self) -> None:
        plan = InstallmentForecastEvidence(
            commitment_id="commitment_partly_malformed",
            display_name="Synthetic Partly Malformed Device",
            charges=(
                charge(
                    "installment-1", "2030-03", "75",
                    installment_number=1, installment_total=3,
                ),
                charge(
                    "malformed", "2030-04", "75",
                    installment_number=None, installment_total=3,
                ),
            ),
        )

        result = self.forecast(plans=[plan])

        self.assertEqual(len(result["unresolved"]), 1)
        self.assertEqual(result["months"][0]["payment_count"], 2)
        self.assertEqual(result["months"][1]["payment_count"], 1)

    def test_cross_card_malformed_installments_are_unresolved_only_for_all_cards(self) -> None:
        plan = InstallmentForecastEvidence(
            commitment_id="commitment_cross_card_malformed",
            display_name="Synthetic Cross-card Device",
            charges=(
                charge(
                    "malformed-a", "2030-04", "75", last4="0001",
                    installment_number=None, installment_total=3,
                ),
                charge(
                    "malformed-b", "2030-05", "75", last4="0002",
                    installment_number=None, installment_total=3,
                ),
            ),
        )

        all_cards = self.forecast(plans=[plan])
        one_card = self.forecast(plans=[plan], card_scope="synthetic:0001")

        self.assertIsNone(all_cards["unresolved"][0]["card"])
        self.assertEqual(one_card["unresolved"], [])
        self.assertEqual(one_card["months"][0]["payment_count"], 1)

    def test_anchor_month_first_installment_advances_later_horizon_months(self) -> None:
        plan = InstallmentForecastEvidence(
            commitment_id="commitment_anchor_start",
            display_name="Synthetic Anchor Device",
            charges=(charge(
                "anchor-installment-1", "2030-04", "1125",
                installment_number=1, installment_total=2,
            ),),
        )

        result = self.forecast(plans=[plan])

        self.assertEqual(result["months"][0]["confirmed_total"], 1125)
        self.assertEqual(result["months"][1]["forecast_total"], 1125)
        final = result["months"][1]["payments"][0]
        self.assertEqual(final["installment_number"], 2)
        self.assertTrue(final["ending"])
        self.assertEqual(result["months"][2]["payment_count"], 0)

    def test_future_first_installment_does_not_create_backward_projection(self) -> None:
        plan = InstallmentForecastEvidence(
            commitment_id="commitment_future_start",
            display_name="Synthetic Future Device",
            charges=(charge(
                "future-installment-1", "2030-05", "100",
                installment_number=1, installment_total=3,
            ),),
        )

        result = self.forecast(plans=[plan])

        self.assertEqual(result["months"][0]["payment_count"], 0)
        self.assertEqual(result["months"][1]["payment_count"], 1)
        self.assertEqual(
            result["months"][1]["payments"][0]["occurrence_status"],
            "unexpected_actual",
        )

    def test_usage_based_amount_aggregates_multiple_charges_by_month(self) -> None:
        charges = [
            charge("jan-a", "2030-01", "100"),
            charge("jan-b", "2030-01", "50"),
            charge("feb-a", "2030-02", "200"),
            charge("feb-b", "2030-02", "25"),
            charge("mar-a", "2030-03", "300"),
            charge("mar-b", "2030-03", "30"),
        ]

        result = self.forecast([profile(
            charges, recurring_type="Usage-based recurring",
        )])
        payment = result["months"][0]["payments"][0]

        self.assertEqual(result["unresolved"], [])
        self.assertEqual(payment["amount"], 225)
        self.assertEqual(payment["recent_range"], [150, 330])

    def test_fixed_component_survives_a_separate_additional_charge(self) -> None:
        evidence = profile([
            charge("jan-a", "2030-01", "100"),
            charge("jan-b", "2030-01", "20"),
            charge("feb", "2030-02", "100"),
            charge("mar", "2030-03", "100"),
        ])

        result = self.forecast([evidence])

        self.assertEqual(result["unresolved"], [])
        self.assertEqual(result["months"][0]["payment_count"], 1)
        payment = result["months"][0]["payments"][0]
        self.assertEqual(payment["amount"], 100)
        self.assertEqual(payment["amount_confidence"], "established")

    def test_ambiguous_fixed_components_keep_the_amount_unknown(self) -> None:
        evidence = profile([
            charge(f"{month}-a", month, "100")
            for month in ("2030-01", "2030-02", "2030-03")
        ] + [
            charge(f"{month}-b", month, "105")
            for month in ("2030-01", "2030-02", "2030-03")
        ])

        payment = self.forecast([evidence])["months"][0]["payments"][0]

        self.assertIsNone(payment["amount"])
        self.assertIsNone(payment["amount_confidence"])

    def test_stable_timing_distinguishes_a_similarly_sized_extra_charge(self) -> None:
        evidence = profile([
            charge(f"{month}-normal", month, "100", day=10)
            for month in ("2030-01", "2030-02", "2030-03")
        ] + [
            charge(f"{month}-extra", month, "102", day=day)
            for month, day in (("2030-01", 20), ("2030-02", 25), ("2030-03", 18))
        ])

        payment = self.forecast([evidence])["months"][0]["payments"][0]

        self.assertEqual(payment["amount"], 100)
        self.assertEqual(payment["amount_confidence"], "established")

    def test_first_anchor_payment_seeds_provisional_later_months(self) -> None:
        evidence = profile([charge("first", "2030-04", "80")])

        result = self.forecast([evidence])

        self.assertEqual(result["months"][0]["payments"][0]["amount_evidence"], "confirmed")
        self.assertIsNone(result["months"][0]["payments"][0]["amount_confidence"])
        for month in result["months"][1:]:
            payment = month["payments"][0]
            self.assertEqual(payment["amount"], 80)
            self.assertEqual(payment["amount_evidence"], "estimate")
            self.assertEqual(payment["amount_confidence"], "provisional")

    def test_two_similar_payments_produce_a_developing_estimate(self) -> None:
        evidence = profile([
            charge("feb", "2030-02", "100"),
            charge("mar", "2030-03", "110"),
        ])

        payment = self.forecast([evidence])["months"][0]["payments"][0]

        self.assertEqual(payment["amount"], 105)
        self.assertEqual(payment["amount_confidence"], "developing")

    def test_two_payment_similarity_uses_the_direct_fifteen_percent_boundary(self) -> None:
        accepted = profile([
            charge("accepted-a", "2030-02", "100"),
            charge("accepted-b", "2030-03", "115"),
        ])
        rejected = profile([
            charge("rejected-a", "2030-02", "100"),
            charge("rejected-b", "2030-03", "115.01"),
        ])

        accepted_payment = self.forecast([accepted])["months"][0]["payments"][0]
        rejected_payment = self.forecast([rejected])["months"][0]["payments"][0]

        self.assertEqual(accepted_payment["amount"], 107.5)
        self.assertEqual(accepted_payment["amount_confidence"], "developing")
        self.assertIsNone(rejected_payment["amount"])
        self.assertIsNone(rejected_payment["amount_confidence"])

    def test_materially_different_two_payment_amounts_are_unknown_in_any_order(self) -> None:
        for first, second in (("75", "100"), ("100", "75")):
            with self.subTest(first=first, second=second):
                evidence = profile([
                    charge("first", "2030-02", first),
                    charge("second", "2030-03", second),
                ])

                payment = self.forecast([evidence])["months"][0]["payments"][0]

                self.assertIsNone(payment["amount"])
                self.assertIsNone(payment["amount_confidence"])

    def test_three_recent_matching_months_establish_a_new_baseline(self) -> None:
        evidence = profile([
            charge(f"old-{month}", month, "100")
            for month in ("2029-10", "2029-11", "2029-12")
        ] + [
            charge(f"new-{month}", month, "150")
            for month in ("2030-01", "2030-02", "2030-03")
        ])

        payment = self.forecast([evidence])["months"][0]["payments"][0]

        self.assertEqual(payment["amount"], 150)
        self.assertEqual(payment["amount_confidence"], "established")

    def test_unresolved_source_prevents_highest_expected_label(self) -> None:
        supported = profile([
            charge("jan", "2030-01", "100"),
            charge("feb", "2030-02", "100"),
            charge("mar", "2030-03", "100"),
            charge("apr", "2030-04", "200"),
        ])
        unsupported = profile([
            charge("other-jan", "2030-01", "50"),
            charge("other-feb", "2030-02", "50"),
            charge("other-mar", "2030-03", "50"),
        ], profile_id="other", display_name="Other", cadence="Irregular")

        result = self.forecast([supported, unsupported])

        self.assertEqual(result["months"][0]["comparison_label"], "highest_known_estimate")

    def test_fixed_amount_allows_one_outlier_among_six_recent_months(self) -> None:
        evidence = profile([
            charge(f"stable-{month}", month, amount)
            for month, amount in (
                ("2029-10", "50"), ("2029-11", "50"), ("2029-12", "50"),
                ("2030-01", "50"), ("2030-02", "50"), ("2030-03", "74.90"),
            )
        ])

        result = self.forecast([evidence])

        self.assertEqual(result["months"][0]["payments"][0]["amount"], 50)

    def test_fixed_amount_rejects_two_outliers_among_six_recent_months(self) -> None:
        evidence = profile([
            charge(f"mixed-{month}", month, amount)
            for month, amount in (
                ("2029-10", "50"), ("2029-11", "50"), ("2029-12", "50"),
                ("2030-01", "50"), ("2030-02", "75"), ("2030-03", "80"),
            )
        ])

        result = self.forecast([evidence])

        self.assertIsNone(result["months"][0]["payments"][0]["amount"])

    def test_out_of_horizon_annual_schedule_skips_card_resolution_warning(self) -> None:
        evidence = profile([
            charge("annual-a", "2029-02", "500", last4="0001"),
            charge("annual-b", "2030-02", "500", last4="0002"),
        ], cadence="Yearly", recurring_type="Scheduled obligation")

        result = self.forecast([evidence])

        self.assertEqual(result["unresolved"], [])
        self.assertTrue(all(not month["payments"] for month in result["months"]))


if __name__ == "__main__":
    unittest.main()
