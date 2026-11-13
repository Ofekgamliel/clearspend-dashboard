from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from clearspend.observations.historical_queries import historical_installments_payload
from tests.synthetic.support import add_import, add_transaction, connect, create_database


class HistoricalInstallmentQueryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.database = Path(self.temporary_directory.name) / "synthetic.db"
        create_database(self.database)

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    def _installment(
        self,
        connection,
        import_id: int,
        *,
        key: str,
        purchase_date: str,
        billing_month: str,
        card: str = "0001",
    ) -> int:
        transaction_id = add_transaction(
            connection,
            import_id,
            key=key,
            merchant="Synthetic Device",
            amount=100,
            category="Electronics",
            transaction_date=purchase_date,
            billing_month=billing_month,
            card_last4=card,
        )
        connection.execute(
            """UPDATE transactions SET original_amount='600.00',
            original_currency='ILS',installment_number=1,installment_total=6
            WHERE id=?""",
            (transaction_id,),
        )
        return transaction_id

    def test_two_purchases_at_one_merchant_keep_separate_plan_identities(self) -> None:
        connection = connect(self.database)
        import_id = add_import(connection)
        self._installment(
            connection,
            import_id,
            key="plan-one",
            purchase_date="2030-01-05",
            billing_month="2030-02",
        )
        self._installment(
            connection,
            import_id,
            key="plan-two",
            purchase_date="2030-01-20",
            billing_month="2030-02",
        )
        connection.commit()
        connection.close()

        payload = historical_installments_payload(
            self.database, ("2030-01", "2030-02"), "all",
        )
        self.assertEqual(payload["2030-01"]["installment_billed"], 0)
        self.assertEqual(payload["2030-02"]["installment_billed"], 200)
        self.assertEqual(len(payload["2030-02"]["plans"]), 2)
        self.assertEqual(len({
            plan["plan_id"] for plan in payload["2030-02"]["plans"]
        }), 2)

    def test_card_filter_and_empty_covered_months_are_preserved(self) -> None:
        connection = connect(self.database)
        import_id = add_import(connection)
        self._installment(
            connection,
            import_id,
            key="selected-card",
            purchase_date="2030-01-05",
            billing_month="2030-02",
        )
        self._installment(
            connection,
            import_id,
            key="other-card",
            purchase_date="2030-01-06",
            billing_month="2030-02",
            card="9999",
        )
        connection.commit()
        connection.close()

        payload = historical_installments_payload(
            self.database,
            ("2030-01", "2030-02"),
            "synthetic:0001",
        )
        self.assertEqual(payload["2030-01"], {
            "installment_billed": 0.0,
            "plans": (),
        })
        self.assertEqual(payload["2030-02"]["installment_billed"], 100)
        self.assertEqual(len(payload["2030-02"]["plans"]), 1)

    def test_no_months_avoids_a_database_read(self) -> None:
        missing = Path(self.temporary_directory.name) / "missing.db"
        self.assertEqual(historical_installments_payload(missing, (), "all"), {})
        self.assertFalse(missing.exists())


if __name__ == "__main__":
    unittest.main()
