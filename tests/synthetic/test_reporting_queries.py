from __future__ import annotations

import tempfile
import unittest
from datetime import date
from pathlib import Path

from clearspend.reporting.queries import period_bounds
from tests.synthetic.support import add_import, add_income, add_transaction, connect, create_database


class ReportingQueryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.database = Path(self.temporary_directory.name) / "synthetic.db"
        create_database(self.database)

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    def test_empty_database_has_no_period_bounds(self) -> None:
        connection = connect(self.database)
        try:
            self.assertEqual(
                period_bounds(connection, "month", today=date(2030, 1, 15)),
                (None, None, "No transactions"),
            )
        finally:
            connection.close()

    def test_coverage_combines_transactions_and_income(self) -> None:
        connection = connect(self.database)
        try:
            import_id = add_import(connection)
            add_transaction(
                connection, import_id, key="early-coverage", merchant="Synthetic Store",
                amount=10, category="General", transaction_date="2029-11-20", billing_month="2029-11",
            )
            add_income(connection, month="2030-02", source_name="Synthetic income", amount=100)
            connection.commit()
            self.assertEqual(
                period_bounds(connection, "all", today=date(2030, 3, 1)),
                ("2029-11-01", "2030-02-01", "Nov 2029 – Feb 2030"),
            )
        finally:
            connection.close()
