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
