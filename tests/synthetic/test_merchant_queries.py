from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from clearspend.merchants.queries import mapping_payload, merchants_payload
from tests.synthetic.support import add_import, add_transaction, connect, create_database


class MerchantQueryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.database = Path(self.temporary_directory.name) / "synthetic.db"
        create_database(self.database)

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    def test_mapping_payload_reports_unresolved_merchants_and_import_coverage(self) -> None:
        connection = connect(self.database)
        import_id = add_import(connection, name="synthetic-statement.xlsx")
        add_transaction(
            connection, import_id, key="known", merchant="Synthetic Known",
            amount=20, category="Household",
        )
        unknown_id = add_transaction(
            connection, import_id, key="unknown", merchant="Synthetic Unknown",
            amount=35, category="Temporary",
        )
        connection.execute(
            "UPDATE transactions SET user_category=NULL,provider_category=NULL WHERE id=?",
            (unknown_id,),
        )
        connection.execute(
            """UPDATE imports SET statement_range='2030-01',parsed_rows=2,
            inserted_rows=2,duplicate_rows=0 WHERE id=?""",
            (import_id,),
        )
        connection.execute(
            """INSERT INTO import_coverage(
            import_id,card_last4,statement_month,statement_period,purchase_date_from,
            purchase_date_to,finalized_rows,official_total
            ) VALUES(?,?,?,?,?,?,?,?)""",
            (import_id, "0001", "2030-01", "2030-01", "2030-01-01", "2030-01-31", 2, "55.00"),
        )
        connection.commit()
        connection.close()

        payload = mapping_payload(self.database)

        self.assertEqual(payload["summary"], {
            "merchants": 2,
            "needs_review": 1,
            "categorized": 1,
        })
        self.assertEqual(payload["review_merchants"][0]["merchant_normalized"], "synthetic unknown")
        self.assertEqual(payload["review_merchants"][0]["amount"], 35)
        self.assertEqual(payload["category_suggestions"], ["Household"])
        self.assertEqual(payload["recent_imports"][0]["original_name"], "synthetic-statement.xlsx")
        self.assertEqual(payload["recent_imports"][0]["coverage"][0]["official_total"], "55.00")

    def test_merchants_payload_groups_aliases_and_preserves_alias_categories(self) -> None:
        connection = connect(self.database)
        import_id = add_import(connection)
        alpha = "Synthetic Alpha".casefold()
        beta = "Synthetic Beta".casefold()
        add_transaction(
            connection, import_id, key="alpha-1", merchant="Synthetic Alpha",
            amount=10, category="Category A", transaction_date="2030-01-10",
        )
        add_transaction(
            connection, import_id, key="alpha-2", merchant="Synthetic Alpha",
            amount=15, category="Category A", transaction_date="2030-02-10",
            billing_month="2030-02",
        )
        add_transaction(
            connection, import_id, key="beta-1", merchant="Synthetic Beta",
            amount=20, category="Category B", transaction_date="2030-03-10",
            billing_month="2030-03",
        )
        for alias, category in ((alpha, "Category A"), (beta, "Category B")):
            connection.execute(
                """INSERT INTO merchant_display_mappings(
                merchant_normalized,canonical_group_id,display_name,updated_at
                ) VALUES(?,?,?,?)""",
                (alias, "synthetic-group", "Synthetic Brand", "2030-03-15T00:00:00"),
            )
            connection.execute(
                """INSERT INTO merchant_mappings(
                merchant_normalized,category,subcategory,updated_at
                ) VALUES(?,?,NULL,?)""",
                (alias, category, "2030-03-15T00:00:00"),
            )
        connection.execute(
            """INSERT INTO recurring_profiles(
            canonical_group_id,display_name,verdict,recurring_type,cadence,
            cadence_months,lifecycle_status,updated_at
            ) VALUES(?,?,?,?,?,?,?,?)""",
            (
                "synthetic-group", "Synthetic Brand", "recurring", "Fixed recurring",
                "Monthly", 1, "active", "2030-03-15T00:00:00",
            ),
        )
        connection.execute(
            """INSERT INTO recurring_profile_members(
            canonical_group_id,merchant_normalized,included,updated_at
            ) VALUES(?,?,?,?)""",
            ("synthetic-group", alpha, 1, "2030-03-15T00:00:00"),
        )
        connection.commit()
        connection.close()

        payload = merchants_payload(self.database)

        self.assertEqual(payload["summary"], {
            "display_identities": 1,
            "mapped_aliases": 2,
            "transactions": 3,
            "multiple_categories": 1,
            "recurring": 1,
        })
        merchant = payload["merchants"][0]
        self.assertEqual(merchant["display_name"], "Synthetic Brand")
        self.assertEqual(merchant["transactions"], 3)
        self.assertEqual(merchant["amount"], 45)
        self.assertEqual(merchant["last_seen"], "2030-03-10")
        self.assertEqual(set(merchant["categories"]), {"Category A", "Category B"})
        self.assertEqual(merchant["recurring_profile"]["included_aliases"], [alpha])
        aliases = {item["merchant_normalized"]: item for item in merchant["aliases"]}
        self.assertTrue(aliases[alpha]["recurring_included"])
        self.assertFalse(aliases[beta]["recurring_included"])

    def test_ungrouped_merchant_uses_latest_raw_name_and_dominant_category(self) -> None:
        connection = connect(self.database)
        import_id = add_import(connection)
        add_transaction(
            connection, import_id, key="older", merchant="Synthetic Original",
            amount=10, category="Category A", transaction_date="2030-01-10",
        )
        newer_id = add_transaction(
            connection, import_id, key="newer", merchant="Synthetic Original",
            amount=20, category="Category A", transaction_date="2030-02-10",
            billing_month="2030-02",
        )
        connection.execute(
            "UPDATE transactions SET merchant_raw='Synthetic Latest Label' WHERE id=?",
            (newer_id,),
        )
        connection.commit()
        connection.close()

        merchant = merchants_payload(self.database)["merchants"][0]

        self.assertEqual(merchant["canonical_group_id"], "synthetic original")
        self.assertEqual(merchant["display_name"], "Synthetic Latest Label")
        self.assertEqual(merchant["categories"], ["Category A"])
        self.assertIsNone(merchant["recurring_profile"])


if __name__ == "__main__":
    unittest.main()
