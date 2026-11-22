from __future__ import annotations

import sqlite3
import tempfile
import unittest
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import patch

from clearspend.events.service import create_event
from clearspend.reporting.category_queries import categories_payload
from clearspend.reporting.dashboard import dashboard_payload
from clearspend.transactions.queries import transactions_payload
from clearspend.transactions.service import (
    save_transaction_adjustment,
    save_transaction_category,
)
from tests.synthetic.support import add_import, add_income, add_transaction, connect, create_database


class SyntheticReportingContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.database_path = Path(self.temporary_directory.name) / "synthetic.db"
        create_database(self.database_path)

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    def test_empty_month_dashboard_preserves_the_no_data_contract(self) -> None:
        payload = dashboard_payload(self.database_path, "month", "all")

        self.assertEqual(payload["period"], {
            "key": "month",
            "start": None,
            "end": None,
            "label": "No transactions",
        })
        self.assertEqual(payload["metrics"]["transactions"], 0)
        self.assertEqual(payload["trend"], [])
        self.assertIsNone(payload["purchase_activity_summary"])

    def test_reimbursement_preserves_charge_and_reduces_personal_spending(self) -> None:
        connection = connect(self.database_path)
        try:
            import_id = add_import(connection)
            transaction_id = add_transaction(
                connection,
                import_id,
                key="reimbursed-purchase",
                merchant="Synthetic Travel Desk",
                amount=1000,
                category="Travel",
            )
            add_income(connection, month="2030-01", source_name="Synthetic salary", amount=2000)
            connection.commit()
        finally:
            connection.close()

        save_transaction_adjustment(
            self.database_path,
            transaction_id,
            750,
            "2030-01-11",
            "Synthetic reimbursement",
        )

        dashboard = dashboard_payload(self.database_path, "month", "all", "2030-01")
        transaction = transactions_payload(
            self.database_path, "month", "all", month="2030-01"
        )["transactions"][0]

        self.assertEqual(transaction["amount"], 1000)
        self.assertEqual(transaction["reimbursed_amount"], 750)
        self.assertEqual(transaction["personal_amount"], 250)
        self.assertEqual(dashboard["metrics"]["spent"], 250)
        self.assertEqual(dashboard["income_summary"]["charges"], 1000)
        self.assertEqual(dashboard["income_summary"]["remaining"], 1750)

    def test_transaction_override_does_not_rewrite_merchant_mapping(self) -> None:
        connection = connect(self.database_path)
        try:
            import_id = add_import(connection)
            connection.execute(
                """INSERT INTO merchant_mappings(
                merchant_normalized,category,subcategory,updated_at
                ) VALUES(?,?,NULL,?)""",
                ("synthetic academy", "General spending", "2030-01-01T00:00:00"),
            )
            transaction_id = add_transaction(
                connection,
                import_id,
                key="academy-purchase",
                merchant="Synthetic Academy",
                amount=300,
                category="General spending",
            )
            connection.commit()
        finally:
            connection.close()

        save_transaction_category(self.database_path, transaction_id, "Education", "")

        connection = sqlite3.connect(self.database_path)
        try:
            merchant_category = connection.execute(
                "SELECT category FROM merchant_mappings WHERE merchant_normalized=?",
                ("synthetic academy",),
            ).fetchone()[0]
        finally:
            connection.close()
        transaction = transactions_payload(
            self.database_path, "month", "all", month="2030-01"
        )["transactions"][0]

        self.assertEqual(merchant_category, "General spending")
        self.assertEqual(transaction["category"], "Education")
        self.assertEqual(transaction["category_source"], "transaction_override")

    def test_routine_scope_excludes_event_transaction_without_changing_all_spending(self) -> None:
        connection = connect(self.database_path)
        try:
            import_id = add_import(connection)
            event_transaction_id = add_transaction(
                connection,
                import_id,
                key="event-purchase",
                merchant="Synthetic Hotel",
                amount=400,
                category="Accommodation",
            )
            add_transaction(
                connection,
                import_id,
                key="routine-purchase",
                merchant="Synthetic Grocer",
                amount=100,
                category="Groceries",
            )
            connection.commit()
        finally:
            connection.close()

        event = create_event(
            self.database_path,
            "Synthetic weekend",
            "trip",
            "2030-01-09",
            "2030-01-12",
            "",
            "completed",
        )["event"]
        connection = connect(self.database_path)
        try:
            connection.execute(
                "INSERT INTO event_transactions(transaction_id,event_id,assigned_at) VALUES(?,?,?)",
                (event_transaction_id, event["id"], "2030-01-15T10:00:00"),
            )
            connection.commit()
        finally:
            connection.close()

        all_spending = categories_payload(
            self.database_path, "month", "all", "2030-01", "all"
        )
        routine_spending = categories_payload(
            self.database_path, "month", "all", "2030-01", "routine"
        )

        self.assertEqual(all_spending["total"], 500)
        self.assertEqual(routine_spending["total"], 100)
        self.assertEqual(
            [item["category"] for item in routine_spending["categories"]], ["Groceries"]
        )

    def test_dashboard_payload_keeps_core_frontend_contract(self) -> None:
        connection = connect(self.database_path)
        try:
            import_id = add_import(connection)
            add_transaction(
                connection,
                import_id,
                key="contract-purchase",
                merchant="Synthetic Store",
                amount=75,
                category="Household",
            )
            connection.commit()
        finally:
            connection.close()

        payload = dashboard_payload(self.database_path, "month", "all", "2030-01")

        self.assertTrue(
            {
                "period",
                "selected_card",
                "metrics",
                "income_summary",
                "cards",
                "categories",
                "recent_transactions",
                "trend",
                "trend_mode",
                "insights",
                "available_months",
            }.issubset(payload)
        )
        self.assertTrue(
            {"spent", "refunds", "transactions", "daily_average", "active_days"}.issubset(
                payload["metrics"]
            )
        )
        self.assertEqual(payload["period"]["key"], "month")
        self.assertEqual(payload["metrics"]["spent"], 75)

    def test_dashboard_uses_a_bounded_number_of_snapshot_queries(self) -> None:
        class CountingConnection:
            def __init__(self, connection):
                self.connection = connection
                self.execute_count = 0

            def execute(self, *args, **kwargs):
                self.execute_count += 1
                return self.connection.execute(*args, **kwargs)

        @contextmanager
        def bound_connection(connection):
            yield connection

        connection = connect(self.database_path)
        import_id = add_import(connection)
        add_transaction(
            connection,
            import_id,
            key="query-count-purchase",
            merchant="Synthetic Store",
            amount=75,
            category="Household",
        )
        connection.commit()
        counted = CountingConnection(connection)
        try:
            with patch(
                "clearspend.reporting.dashboard.database_connection",
                return_value=bound_connection(counted),
            ):
                dashboard_payload(self.database_path, "month", "all", "2030-01")
        finally:
            connection.close()

        self.assertEqual(counted.execute_count, 13)

    def test_daily_average_uses_the_displayed_spending_total(self) -> None:
        connection = connect(self.database_path)
        try:
            import_id = add_import(connection)
            add_transaction(
                connection,
                import_id,
                key="rounding-day-one",
                merchant="Synthetic Store One",
                amount=10.01,
                category="Household",
                transaction_date="2030-01-10",
            )
            add_transaction(
                connection,
                import_id,
                key="rounding-day-two",
                merchant="Synthetic Store Two",
                amount=10.02,
                category="Household",
                transaction_date="2030-01-11",
            )
            connection.commit()
        finally:
            connection.close()

        metrics = dashboard_payload(
            self.database_path, "month", "all", "2030-01"
        )["metrics"]

        self.assertEqual(metrics["active_days"], 2)
        self.assertEqual(
            metrics["daily_average"],
            round(metrics["spent"] / metrics["active_days"], 2),
        )


if __name__ == "__main__":
    unittest.main()
