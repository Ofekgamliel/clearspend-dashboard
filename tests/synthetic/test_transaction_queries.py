from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from clearspend.transactions.queries import transactions_payload
from tests.synthetic.support import add_import, add_transaction, connect, create_database


class TransactionQueryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.database = Path(self.temporary_directory.name) / "synthetic.db"
        create_database(self.database)

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    def test_search_matches_canonical_display_name_and_effective_category(self) -> None:
        connection = connect(self.database)
        try:
            import_id = add_import(connection)
            transaction_id = add_transaction(
                connection, import_id, key="searchable", merchant="Opaque Statement Text",
                amount=40, category="Original",
            )
            connection.execute(
                """INSERT INTO merchant_display_mappings(
                merchant_normalized,canonical_group_id,display_name,updated_at
                ) VALUES('opaque statement text','synthetic-group','Friendly Search Name','2030-01-01')"""
            )
            connection.execute(
                """INSERT INTO transaction_category_overrides(
                transaction_id,category,subcategory,updated_at
                ) VALUES(?,'Special Category',NULL,'2030-01-01')""",
                (transaction_id,),
            )
            connection.commit()
        finally:
            connection.close()

        display_result = transactions_payload(
            self.database, "all", "all", search="Search Name"
        )
        category_result = transactions_payload(
            self.database, "all", "all", search="special cat"
        )
        self.assertEqual(display_result["total"], 1)
        self.assertEqual(category_result["transactions"][0]["category"], "Special Category")

    def test_browsing_limit_does_not_limit_nonempty_search(self) -> None:
        connection = connect(self.database)
        try:
            import_id = add_import(connection)
            for index in range(1001):
                add_transaction(
                    connection, import_id, key=f"bulk-{index}",
                    merchant="Unique Needle Merchant" if index == 0 else f"Synthetic Merchant {index}",
                    amount=1, category="General",
                )
            connection.commit()
        finally:
            connection.close()

        browse = transactions_payload(self.database, "all", "all")
        search = transactions_payload(self.database, "all", "all", search="Needle")
        self.assertEqual(browse["total"], 1001)
        self.assertEqual(len(browse["transactions"]), 1000)
        self.assertEqual(search["total"], 1)
        self.assertEqual(search["transactions"][0]["merchant_raw"], "Unique Needle Merchant")
