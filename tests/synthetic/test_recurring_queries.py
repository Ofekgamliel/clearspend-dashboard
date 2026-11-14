from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from clearspend.recurring.queries import recurring_payload
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
