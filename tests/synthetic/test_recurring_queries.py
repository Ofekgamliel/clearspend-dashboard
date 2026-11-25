from __future__ import annotations

import tempfile
import unittest
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from unittest.mock import patch
from zoneinfo import ZoneInfo

from clearspend.recurring.queries import recurring_payload, upcoming_payload
from clearspend.recurring.service import manage_recurring_profile
from tests.synthetic.support import add_import, add_transaction, connect, create_database


class RecurringQueryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.database = Path(self.temporary_directory.name) / "synthetic.db"
        create_database(self.database)

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    def test_reviewed_profile_is_reported_and_respects_card_filter(self) -> None:
        connection = connect(self.database)
        try:
            import_id = add_import(connection)
            for month, amount in (("2030-01", 50), ("2030-02", 55)):
                add_transaction(
                    connection, import_id, key=f"subscription-{month}",
                    merchant="Synthetic Subscription", amount=amount, category="Subscriptions",
                    transaction_date=f"{month}-10", billing_month=month,
                )
            connection.commit()
        finally:
            connection.close()
        manage_recurring_profile(
            self.database, "synthetic subscription", "recurring", "Fixed recurring",
            "Monthly", "active", "",
        )

        payload = recurring_payload(self.database, "month", "all", "2030-02")
        self.assertEqual(payload["metrics"]["recurring_billed"], 55)
        self.assertEqual(payload["series"][0]["display_name"], "Synthetic Subscription")
        self.assertEqual(payload["series"][0]["status"], "confirmed")
        self.assertEqual(
            recurring_payload(self.database, "month", "synthetic:9999", "2030-02")["series"],
            [],
        )

    def test_installment_rows_are_collapsed_into_one_commitment(self) -> None:
        connection = connect(self.database)
        try:
            import_id = add_import(connection)
            ids = []
            for number, month in ((1, "2030-01"), (2, "2030-02")):
                ids.append(add_transaction(
                    connection, import_id, key=f"installment-{number}", merchant="Synthetic Device",
                    amount=100, category="Electronics", transaction_date="2030-01-05",
                    billing_month=month,
                ))
            for number, transaction_id in enumerate(ids, start=1):
                connection.execute(
                    """UPDATE transactions SET original_amount='400.00',original_currency='ILS',
                    installment_number=?,installment_total=4 WHERE id=?""",
                    (number, transaction_id),
                )
            connection.commit()
        finally:
            connection.close()

        payload = recurring_payload(self.database, "all", "all")
        commitment = payload["commitments"][0]
        self.assertEqual(commitment["progress"], "2 / 4")
        self.assertEqual(commitment["paid"], 200)
        self.assertEqual(commitment["remaining"], 200)
        self.assertEqual(payload["metrics"]["installment_plans"], 1)

    def test_selected_alias_history_and_installment_totals_remain_separate(self) -> None:
        connection = connect(self.database)
        try:
            import_id = add_import(connection)
            included = "synthetic health service"
            excluded = "synthetic health shop"
            for alias, amount in ((included, 120), (excluded, 80)):
                add_transaction(
                    connection, import_id, key=f"alias-{alias}", merchant=alias.title(),
                    amount=amount, category="Health", transaction_date="2030-02-10",
                    billing_month="2030-02",
                )
                connection.execute(
                    """INSERT INTO merchant_display_mappings(
                    merchant_normalized,canonical_group_id,display_name,updated_at
                    ) VALUES(?,'synthetic-health','Synthetic Health','2030-02-01')""",
                    (alias,),
                )
            installment_id = add_transaction(
                connection, import_id, key="separate-installment", merchant="Synthetic Device",
                amount=40, category="Electronics", transaction_date="2030-02-11",
                billing_month="2030-02",
            )
            connection.execute(
                """UPDATE transactions SET original_amount='120.00',original_currency='ILS',
                installment_number=1,installment_total=3 WHERE id=?""",
                (installment_id,),
            )
            connection.commit()
        finally:
            connection.close()

        manage_recurring_profile(
            self.database, "synthetic-health", "recurring", "Fixed recurring", "Monthly",
            "active", "", [included],
        )

        payload = recurring_payload(self.database, "month", "all", "2030-02")
        self.assertEqual(payload["metrics"]["recurring_billed"], 120)
        self.assertEqual(payload["metrics"]["installment_billed"], 40)
        self.assertEqual(payload["series"][0]["source_aliases"], [included.title()])
        self.assertEqual(payload["series"][0]["history"][-1]["amount"], 120)

    def test_upcoming_query_uses_reviewed_positive_rows_and_an_injected_clock(self) -> None:
        connection = connect(self.database)
        try:
            import_id = add_import(connection)
            for month, amount in (
                ("2030-01", 100), ("2030-02", 100), ("2030-03", 100),
                ("2030-04", 110),
            ):
                add_transaction(
                    connection,
                    import_id,
                    key=f"upcoming-{month}",
                    merchant="Synthetic Forecast",
                    amount=amount,
                    category="Subscriptions",
                    transaction_date=f"{month}-10",
                    billing_month=month,
                )
            add_transaction(
                connection,
                import_id,
                key="upcoming-refund",
                merchant="Synthetic Forecast",
                amount=-25,
                category="Subscriptions",
                transaction_date="2030-04-11",
                billing_month="2030-04",
            )
            connection.execute(
                """UPDATE transactions SET transaction_date='2030-03-29',
                billing_date='2030-04-12' WHERE transaction_key='upcoming-2030-04'"""
            )
            connection.commit()
        finally:
            connection.close()
        manage_recurring_profile(
            self.database, "synthetic forecast", "recurring", "Fixed recurring",
            "Monthly", "active", "",
        )

        payload = upcoming_payload(
            self.database,
            "all",
            clock=lambda: datetime(2030, 4, 2, 10, tzinfo=ZoneInfo("Asia/Jerusalem")),
        )

        self.assertEqual(payload["anchor_month"], "2030-04")
        self.assertEqual(payload["horizon_end"], "2030-06")
        self.assertEqual(payload["months"][0]["confirmed_total"], 110)
        self.assertEqual(payload["months"][0]["payment_count"], 1)
        self.assertEqual(
            payload["months"][0]["payments"][0]["expected_date"], "2030-04-12"
        )
        self.assertEqual(payload["months"][1]["forecast_total"], 100)
        self.assertEqual(payload["generated_as_of"], "2030-04-02T10:00:00+03:00")
        self.assertNotIn("upcoming-2030-04", repr(payload))
        self.assertTrue(all(
            month["comparison_label"] in {
                None, "highest_expected", "highest_known_estimate",
            }
            for month in payload["months"]
        ))

    def test_unknown_stored_cadence_ignores_stale_numeric_interval(self) -> None:
        connection = connect(self.database)
        try:
            import_id = add_import(connection)
            for month in ("2030-01", "2030-02", "2030-03"):
                add_transaction(
                    connection,
                    import_id,
                    key=f"legacy-cadence-{month}",
                    merchant="Synthetic Legacy Cadence",
                    amount=50,
                    category="Subscriptions",
                    transaction_date=f"{month}-10",
                    billing_month=month,
                )
            connection.commit()
        finally:
            connection.close()
        manage_recurring_profile(
            self.database, "synthetic legacy cadence", "recurring",
            "Fixed recurring", "Monthly", "active", "",
        )
        connection = connect(self.database)
        try:
            connection.execute(
                """UPDATE recurring_profiles SET cadence='Biweekly',cadence_months=1
                WHERE canonical_group_id='synthetic legacy cadence'"""
            )
            connection.commit()
        finally:
            connection.close()

        payload = upcoming_payload(
            self.database,
            "all",
            clock=lambda: datetime(
                2030, 4, 2, 10, tzinfo=ZoneInfo("Asia/Jerusalem")
            ),
        )

        self.assertEqual(payload["unresolved"][0]["reason"], "unsupported_cadence")
        self.assertTrue(all(not month["payments"] for month in payload["months"]))

    def test_total_only_malformed_installment_never_enters_recurring_evidence(self) -> None:
        connection = connect(self.database)
        try:
            import_id = add_import(connection)
            transaction_id = add_transaction(
                connection,
                import_id,
                key="malformed-total-only",
                merchant="Synthetic Malformed Subscription",
                amount=90,
                category="Subscriptions",
                transaction_date="2030-04-10",
                billing_month="2030-04",
            )
            connection.execute(
                """UPDATE transactions SET original_amount='270.00',
                original_currency='ILS',installment_total=3 WHERE id=?""",
                (transaction_id,),
            )
            connection.commit()
        finally:
            connection.close()
        manage_recurring_profile(
            self.database,
            "synthetic malformed subscription",
            "recurring",
            "Fixed recurring",
            "Monthly",
            "active",
            "",
        )

        payload = upcoming_payload(
            self.database,
            "all",
            clock=lambda: datetime(
                2030, 4, 2, 10, tzinfo=ZoneInfo("Asia/Jerusalem")
            ),
        )
        payments = [
            payment for month in payload["months"] for payment in month["payments"]
        ]

        self.assertEqual(len(payments), 1)
        self.assertEqual(payments[0]["payment_type"], "Installment")
        self.assertEqual(payments[0]["occurrence_status"], "unexpected_actual")
        self.assertIn(
            "invalid_installment_evidence",
            {item["reason"] for item in payload["unresolved"]},
        )

    def test_upcoming_uses_two_bounded_bulk_queries(self) -> None:
        connection = connect(self.database)
        statements: list[str] = []
        connection.set_trace_callback(statements.append)

        @contextmanager
        def existing_connection(_database):
            yield connection

        try:
            with patch(
                "clearspend.recurring.queries.database_connection",
                existing_connection,
            ):
                upcoming_payload(
                    self.database,
                    "all",
                    clock=lambda: datetime(
                        2030, 4, 2, 10, tzinfo=ZoneInfo("Asia/Jerusalem")
                    ),
                )
        finally:
            connection.close()

        selects = [sql for sql in statements if sql.lstrip().upper().startswith("SELECT")]
        self.assertEqual(len(selects), 2)
        self.assertTrue(all(
            "BETWEEN '2028-04' AND '2030-06'" in sql for sql in selects
        ))
