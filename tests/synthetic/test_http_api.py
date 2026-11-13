from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from clearspend.http.api import (
    JSON_GET_PATHS,
    JSON_POST_PATHS,
    dispatch_json_get,
    dispatch_json_post,
)
from tests.synthetic.support import add_import, add_transaction, connect, create_database


class HttpApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.database = Path(self.temporary_directory.name) / "synthetic.db"
        create_database(self.database)

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    def test_mapping_route_preserves_service_result_and_status(self) -> None:
        connection = connect(self.database)
        import_id = add_import(connection)
        add_transaction(
            connection, import_id, key="mapped", merchant="Synthetic Shop",
            amount=20, category="Old",
        )
        connection.commit()
        connection.close()

        result, status = dispatch_json_post(self.database, "/api/mapping", {
            "merchant_normalized": "synthetic shop",
            "category": "Household",
            "subcategory": "Supplies",
        })

        self.assertEqual(status, 200)
        self.assertEqual(result["transactions_updated"], 1)
        connection = connect(self.database)
        category = connection.execute(
            "SELECT user_category FROM transactions WHERE merchant_normalized='synthetic shop'"
        ).fetchone()[0]
        connection.close()
        self.assertEqual(category, "Household")

    def test_event_creation_route_returns_created_status(self) -> None:
        result, status = dispatch_json_post(self.database, "/api/events", {
            "name": "Synthetic Conference",
            "event_type": "business_trip",
            "destination": "Synthetic City",
            "start_date": "2030-04-10",
            "end_date": "2030-04-12",
            "status": "planned",
        })

        self.assertEqual(status, 201)
        self.assertEqual(result["event"]["name"], "Synthetic Conference")
        self.assertEqual(result["event"]["destination"], "Synthetic City")

    def test_alias_shape_and_unknown_route_are_rejected(self) -> None:
        self.assertIn("/api/merchants", JSON_POST_PATHS)
        with self.assertRaisesRegex(ValueError, "Aliases must be a list"):
            dispatch_json_post(self.database, "/api/merchants", {"aliases": "invalid"})
        with self.assertRaisesRegex(ValueError, "Unknown JSON API route"):
            dispatch_json_post(self.database, "/api/not-real", {})

    def test_get_defaults_and_health_contract(self) -> None:
        connection = connect(self.database)
        import_id = add_import(connection)
        add_transaction(
            connection, import_id, key="dashboard-default", merchant="Synthetic Merchant",
            amount=20, category="Household",
        )
        connection.commit()
        connection.close()

        health, status = dispatch_json_get(self.database, "/api/health", {})
        dashboard, dashboard_status = dispatch_json_get(
            self.database, "/api/dashboard", {}
        )

        self.assertEqual(status, 200)
        self.assertEqual(health, {"status": "ok", "mode": "local", "database": True})
        self.assertEqual(dashboard_status, 200)
        self.assertEqual(dashboard["period"]["key"], "month")
        self.assertEqual(dashboard["selected_card"], "all")

    def test_get_period_and_scope_validation_are_consistent(self) -> None:
        self.assertIn("/api/transactions", JSON_GET_PATHS)
        with self.assertRaisesRegex(ValueError, "Invalid period"):
            dispatch_json_get(
                self.database, "/api/dashboard", {"period": ["invalid"]}
            )
        with self.assertRaisesRegex(ValueError, "Invalid event scope"):
            dispatch_json_get(
                self.database,
                "/api/transactions",
                {"period": ["all"], "event_scope": ["invalid"]},
            )
        with self.assertRaisesRegex(ValueError, "Unknown JSON API route"):
            dispatch_json_get(self.database, "/api/not-real", {})

    def test_transaction_get_forwards_search_and_category_filters(self) -> None:
        connection = connect(self.database)
        import_id = add_import(connection)
        add_transaction(
            connection, import_id, key="matching", merchant="Synthetic Search Merchant",
            amount=30, category="Travel",
        )
        add_transaction(
            connection, import_id, key="other", merchant="Synthetic Other Merchant",
            amount=20, category="Household",
        )
        connection.commit()
        connection.close()

        payload, status = dispatch_json_get(
            self.database,
            "/api/transactions",
            {"period": ["all"], "q": ["search"], "category": ["Travel"]},
        )

        self.assertEqual(status, 200)
        self.assertEqual(payload["total"], 1)
        self.assertEqual(payload["transactions"][0]["merchant_raw"], "Synthetic Search Merchant")


if __name__ == "__main__":
    unittest.main()
