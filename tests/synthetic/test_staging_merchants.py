from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from clearspend.staging.merchants import (
    add_staged_merchant_transactions,
    resolve_staged_merchants,
)
from tests.synthetic.support import connect, create_database


def transaction(key: str, **overrides):
    values = {
        "transaction_key": key,
        "merchant_normalized": "synthetic merchant",
        "merchant_raw": "Synthetic Merchant",
        "transaction_date": "2030-02-10",
        "charged_amount": "40.00",
        "provider": "synthetic",
        "card_last4": "0001",
        "provider_category": "Provider category",
    }
    values.update(overrides)
    return SimpleNamespace(**values)


class StagingMerchantTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.database = Path(self.temporary_directory.name) / "synthetic.db"
        create_database(self.database)

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    def test_aggregation_excludes_exact_and_pending_rows(self) -> None:
        groups: dict[str, dict] = {}
        add_staged_merchant_transactions(
            groups,
            [
                transaction("included", charged_amount="-40.00"),
                transaction("duplicate"),
                transaction("pending"),
            ],
            duplicate_keys={"duplicate"},
            pending_keys={"pending"},
        )

        group = groups["synthetic merchant"]
        self.assertEqual(group["transactions"], 1)
        self.assertEqual(group["amount"], 40)
        self.assertEqual(group["provider_categories"].most_common(1), [("Provider category", 1)])

    def test_aggregation_tracks_date_span_cards_and_dominant_provider_category(self) -> None:
        groups: dict[str, dict] = {}
        add_staged_merchant_transactions(
            groups,
            [
                transaction("first", transaction_date="2030-03-10", card_last4="0002"),
                transaction("second", transaction_date="2030-01-05"),
                transaction("third", transaction_date="2030-04-20", provider_category="Other"),
            ],
            duplicate_keys=set(),
            pending_keys=set(),
        )

        group = groups["synthetic merchant"]
        self.assertEqual(group["first_date"], "2030-01-05")
        self.assertEqual(group["last_date"], "2030-04-20")
        self.assertEqual(group["cards"], {"0001", "0002"})
        self.assertEqual(group["provider_categories"].most_common(1)[0][0], "Provider category")

    def test_database_mapping_has_priority_over_provider_suggestion(self) -> None:
        groups: dict[str, dict] = {}
        add_staged_merchant_transactions(
            groups,
            [transaction("included")],
            duplicate_keys=set(),
            pending_keys=set(),
        )
        connection = connect(self.database)
        connection.execute(
            """INSERT INTO merchant_mappings(
            merchant_normalized,category,subcategory,updated_at
            ) VALUES(?,?,?,?)""",
            ("synthetic merchant", "Reviewed category", "Reviewed subcategory", "2030-01-15"),
        )
        connection.execute(
            """INSERT INTO merchant_display_mappings(
            merchant_normalized,canonical_group_id,display_name,updated_at
            ) VALUES(?,?,?,?)""",
            ("synthetic merchant", "synthetic-group", "Synthetic Display", "2030-01-15"),
        )
        connection.commit()

        merchants = resolve_staged_merchants(connection, groups)
        connection.close()

        self.assertEqual(merchants[0]["category"], "Reviewed category")
        self.assertEqual(merchants[0]["subcategory"], "Reviewed subcategory")
        self.assertEqual(merchants[0]["display_name"], "Synthetic Display")
        self.assertEqual(merchants[0]["match_source"], "exact_db")
        self.assertFalse(merchants[0]["needs_review"])


if __name__ == "__main__":
    unittest.main()
