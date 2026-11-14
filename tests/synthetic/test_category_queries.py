from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from clearspend.reporting.category_queries import categories_payload
from tests.synthetic.support import add_import, add_transaction, connect, create_database


class CategoryQueryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.database = Path(self.temporary_directory.name) / "synthetic.db"
        create_database(self.database)

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    def test_month_payload_compares_categories_with_previous_month(self) -> None:
        connection = connect(self.database)
        try:
            import_id = add_import(connection)
            add_transaction(
                connection, import_id, key="january-fashion", merchant="Synthetic Clothing",
                amount=100, category="Fashion", transaction_date="2030-01-10",
                billing_month="2030-01",
            )
            add_transaction(
                connection, import_id, key="february-fashion", merchant="Synthetic Clothing",
                amount=150, category="Fashion", transaction_date="2030-02-10",
                billing_month="2030-02",
            )
            add_transaction(
                connection, import_id, key="february-travel", merchant="Synthetic Rail",
                amount=50, category="Travel", transaction_date="2030-02-11",
                billing_month="2030-02",
            )
            connection.commit()
        finally:
            connection.close()

        payload = categories_payload(self.database, "month", "all", "2030-02")
        rows = {row["category"]: row for row in payload["categories"]}
        self.assertEqual(payload["total"], 200)
        self.assertEqual(rows["Fashion"]["share"], 75)
        self.assertEqual(rows["Fashion"]["change_percent"], 50)
        self.assertEqual(rows["Travel"]["comparison"], "new")
        self.assertEqual(payload["category_comparison"]["previous_month"], "2030-01")

    def test_card_selection_limits_category_totals(self) -> None:
        connection = connect(self.database)
        try:
            import_id = add_import(connection)
            add_transaction(
                connection, import_id, key="card-one", merchant="Synthetic Grocer",
                amount=80, category="Groceries", card_last4="0001",
            )
            add_transaction(
                connection, import_id, key="card-two", merchant="Synthetic Cinema",
                amount=20, category="Leisure", card_last4="0002",
            )
            connection.commit()
        finally:
            connection.close()

        payload = categories_payload(
            self.database, "month", "synthetic:0002", "2030-01"
        )
        self.assertEqual(payload["total"], 20)
        self.assertEqual([row["category"] for row in payload["categories"]], ["Leisure"])
