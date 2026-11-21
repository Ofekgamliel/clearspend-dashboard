from __future__ import annotations

import shutil
import tempfile
import unittest
from pathlib import Path

from clearspend.database.postgresql_parity import (
    FinancialParityError,
    _digest,
    verify_financial_parity,
)
from tests.synthetic.support import (
    add_import,
    add_income,
    add_transaction,
    connect,
    create_database,
)


class PostgreSQLParityTests(unittest.TestCase):
    def test_numeric_json_types_are_compared_by_value(self) -> None:
        self.assertEqual(_digest({"amount": 0}), _digest({"amount": 0.0}))
        self.assertEqual(_digest({"amount": 12}), _digest({"amount": 12.0}))
        self.assertNotEqual(_digest({"amount": 12}), _digest({"amount": 12.01}))

    def databases(self, directory: str) -> tuple[Path, Path]:
        source = Path(directory) / "source.db"
        target = Path(directory) / "target.db"
        create_database(source)
        connection = connect(source)
        import_id = add_import(connection)
        add_transaction(
            connection,
            import_id,
            key="parity-transaction",
            merchant="Synthetic Parity Shop",
            amount=125,
            category="Household",
            transaction_date="2030-03-12",
            billing_month="2030-03",
        )
        add_income(
            connection,
            month="2030-03",
            source_name="Synthetic salary",
            amount=1000,
        )
        connection.commit()
        connection.close()
        shutil.copy2(source, target)
        return source, target

    def test_identical_engines_match_dashboard_and_transaction_presentations(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            source, target = self.databases(directory)

            report = verify_financial_parity(source, target)

        self.assertGreater(report.comparisons, 20)
        self.assertEqual(len(report.snapshot_sha256), 64)

    def test_difference_reports_safe_workflow_names_without_financial_values(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            source, target = self.databases(directory)
            connection = connect(target)
            connection.execute(
                "UPDATE transactions SET charged_amount=? WHERE transaction_key=?",
                (987654, "parity-transaction"),
            )
            connection.commit()
            connection.close()

            with self.assertRaises(FinancialParityError) as captured:
                verify_financial_parity(source, target)

        message = str(captured.exception)
        self.assertIn("dashboard:", message)
        self.assertIn("transactions:", message)
        self.assertNotIn("987654", message)
        self.assertNotIn("Synthetic Parity Shop", message)


if __name__ == "__main__":
    unittest.main()
