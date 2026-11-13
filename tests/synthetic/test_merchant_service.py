from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from clearspend.merchants.service import save_mapping, save_merchant
from tests.synthetic.support import add_import, add_transaction, connect, create_database


class MerchantServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.database = Path(self.temporary_directory.name) / "synthetic.db"
        create_database(self.database)

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    def test_save_mapping_updates_rule_and_matching_transactions(self) -> None:
        connection = connect(self.database)
        import_id = add_import(connection)
        merchant = "Synthetic Shop".casefold()
        first_id = add_transaction(
            connection, import_id, key="mapping-1", merchant="Synthetic Shop",
            amount=10, category="Old",
        )
        second_id = add_transaction(
            connection, import_id, key="mapping-2", merchant="Synthetic Shop",
            amount=20, category="Old",
        )
        connection.execute(
            """INSERT INTO transaction_category_overrides(
            transaction_id,category,subcategory,updated_at
            ) VALUES(?,?,?,?)""",
            (first_id, "One-off", None, "2030-01-01T00:00:00"),
        )
        connection.commit()
        connection.close()

        result = save_mapping(self.database, merchant, "Household", "Supplies")

        connection = connect(self.database)
        mapping = connection.execute(
            "SELECT category,subcategory FROM merchant_mappings WHERE merchant_normalized=?",
            (merchant,),
        ).fetchone()
        transactions = connection.execute(
            "SELECT id,user_category,user_subcategory FROM transactions ORDER BY id"
        ).fetchall()
        override = connection.execute(
            "SELECT category FROM transaction_category_overrides WHERE transaction_id=?",
            (first_id,),
        ).fetchone()
        connection.close()
        self.assertEqual(result["transactions_updated"], 2)
        self.assertEqual(tuple(mapping), ("Household", "Supplies"))
        self.assertEqual(
            [(row[0], row[1], row[2]) for row in transactions],
            [(first_id, "Household", "Supplies"), (second_id, "Household", "Supplies")],
        )
        self.assertEqual(override[0], "One-off")

    def test_save_merchant_updates_identity_and_only_requested_alias_category(self) -> None:
        connection = connect(self.database)
        import_id = add_import(connection)
        alpha = "Synthetic Alpha".casefold()
        beta = "Synthetic Beta".casefold()
        add_transaction(
            connection, import_id, key="merchant-1", merchant="Synthetic Alpha",
            amount=10, category="Old A",
        )
        add_transaction(
            connection, import_id, key="merchant-2", merchant="Synthetic Beta",
            amount=20, category="Old B",
        )
        for alias in (alpha, beta):
            connection.execute(
                """INSERT INTO merchant_display_mappings(
                merchant_normalized,canonical_group_id,display_name,updated_at
                ) VALUES(?,?,?,?)""",
                (alias, "synthetic-group", "Old Brand", "2030-01-01T00:00:00"),
            )
        connection.commit()
        connection.close()

        result = save_merchant(
            self.database,
            "synthetic-group",
            "Household Brand",
            [{"merchant_normalized": alpha, "category": "Household", "subcategory": "Supplies"}],
        )

        connection = connect(self.database)
        identities = connection.execute(
            """SELECT merchant_normalized,display_name FROM merchant_display_mappings
            ORDER BY merchant_normalized"""
        ).fetchall()
        categories = connection.execute(
            "SELECT merchant_normalized,category FROM merchant_mappings ORDER BY merchant_normalized"
        ).fetchall()
        transactions = connection.execute(
            "SELECT merchant_normalized,user_category FROM transactions ORDER BY merchant_normalized"
        ).fetchall()
        connection.close()
        self.assertEqual(result, {
            "status": "saved",
            "display_name": "Household Brand",
            "aliases_updated": 2,
            "category_rules_updated": 1,
            "transactions_updated": 1,
        })
        self.assertEqual(
            [(row[0], row[1]) for row in identities],
            [(alpha, "Household Brand"), (beta, "Household Brand")],
        )
        self.assertEqual([(row[0], row[1]) for row in categories], [(alpha, "Household")])
        self.assertEqual(
            [(row[0], row[1]) for row in transactions],
            [(alpha, "Household"), (beta, "Old B")],
        )

    def test_save_merchant_validation_failure_rolls_back_identity_changes(self) -> None:
        connection = connect(self.database)
        import_id = add_import(connection)
        alias = "Synthetic Alpha".casefold()
        add_transaction(
            connection, import_id, key="rollback-1", merchant="Synthetic Alpha",
            amount=10, category="Old",
        )
        connection.execute(
            """INSERT INTO merchant_display_mappings(
            merchant_normalized,canonical_group_id,display_name,updated_at
            ) VALUES(?,?,?,?)""",
            (alias, "synthetic-group", "Old Brand", "2030-01-01T00:00:00"),
        )
        connection.commit()
        connection.close()

        with self.assertRaisesRegex(ValueError, "needs a category"):
            save_merchant(
                self.database,
                "synthetic-group",
                "New Brand",
                [{"merchant_normalized": alias, "category": "", "subcategory": ""}],
            )

        connection = connect(self.database)
        display_name = connection.execute(
            "SELECT display_name FROM merchant_display_mappings WHERE merchant_normalized=?",
            (alias,),
        ).fetchone()[0]
        mapping_count = connection.execute("SELECT COUNT(*) FROM merchant_mappings").fetchone()[0]
        transaction_category = connection.execute(
            "SELECT user_category FROM transactions WHERE merchant_normalized=?", (alias,)
        ).fetchone()[0]
        connection.close()
        self.assertEqual(display_name, "Old Brand")
        self.assertEqual(mapping_count, 0)
        self.assertEqual(transaction_category, "Old")


if __name__ == "__main__":
    unittest.main()
