from __future__ import annotations

import tempfile
import unittest
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import patch

from clearspend.observations.inputs import load_observation_inputs
from clearspend.recurring.queries import recurring_payload
from clearspend.recurring.service import manage_recurring_profile
from tests.synthetic.support import (
    add_import,
    add_income,
    add_transaction,
    connect,
    create_database,
)


class ObservationInputSnapshotTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.database = Path(self.temporary_directory.name) / "synthetic.db"
        create_database(self.database)
        connection = connect(self.database)
        import_id = add_import(connection)
        self.january_id = add_transaction(
            connection,
            import_id,
            key="january",
            merchant="Synthetic January",
            amount=100,
            category="Food",
            transaction_date="2030-01-10",
            billing_month="2030-01",
        )
        self.february_id = add_transaction(
            connection,
            import_id,
            key="february",
            merchant="Synthetic February",
            amount=200,
            category="Travel",
            transaction_date="2030-02-10",
            billing_month="2030-02",
        )
        add_income(connection, month="2030-01", source_name="Synthetic income", amount=1_000)
        add_income(connection, month="2030-02", source_name="Synthetic income", amount=1_100)
        connection.commit()
        connection.close()

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    def test_month_snapshot_keeps_prior_transaction_history(self) -> None:
        snapshot = load_observation_inputs(
            self.database,
            period="month",
            card="all",
            month="2030-02",
        )
        self.assertEqual(snapshot.scope.target_months, ("2030-02",))
        self.assertEqual(snapshot.scope.history_months, ("2030-01", "2030-02"))
        self.assertEqual(set(snapshot.transactions_by_month), {"2030-01", "2030-02"})
        self.assertEqual(
            snapshot.transactions_by_month["2030-01"][0]["id"],
            self.january_id,
        )
        self.assertEqual(
            snapshot.transactions_by_month["2030-02"][0]["id"],
            self.february_id,
        )

    def test_month_snapshot_loads_only_target_recurring_payload(self) -> None:
        snapshot = load_observation_inputs(
            self.database,
            period="month",
            card="all",
            month="2030-02",
        )
        self.assertEqual(set(snapshot.recurring_by_month), {"2030-02"})
        self.assertEqual(
            snapshot.recurring_by_month["2030-02"]["period"]["key"],
            "month",
        )

    def test_bulk_recurring_snapshot_preserves_monthly_series_contract(self) -> None:
        connection = connect(self.database)
        connection.execute(
            "UPDATE transactions SET merchant_raw=?,merchant_normalized=?",
            ("Synthetic Subscription", "synthetic subscription"),
        )
        connection.commit()
        connection.close()
        manage_recurring_profile(
            self.database,
            "synthetic subscription",
            "recurring",
            "Fixed recurring",
            "Monthly",
            "active",
            "",
        )

        snapshot = load_observation_inputs(
            self.database,
            period="all",
            card="all",
        )

        for month in snapshot.scope.recurring_months:
            expected = recurring_payload(self.database, "month", "all", month)
            self.assertEqual(
                snapshot.recurring_by_month[month]["series"],
                expected["series"],
            )

    def test_all_card_snapshot_supplies_household_history_and_income_visibility(self) -> None:
        snapshot = load_observation_inputs(
            self.database,
            period="all",
            card="all",
        )
        self.assertTrue(snapshot.income_visible)
        self.assertEqual(set(snapshot.household_history), {"2030-01", "2030-02"})
        self.assertEqual(snapshot.household_history["2030-02"]["income"], 1_100)

    def test_income_hidden_and_specific_card_disable_income_observations(self) -> None:
        hidden = load_observation_inputs(
            self.database,
            period="month",
            card="all",
            month="2030-02",
            income_hidden=True,
        )
        card = load_observation_inputs(
            self.database,
            period="month",
            card="synthetic:0001",
            month="2030-02",
        )
        self.assertFalse(hidden.income_visible)
        self.assertFalse(card.income_visible)
        self.assertEqual(card.household_history, {})

    def test_active_review_keys_are_loaded_without_mutating_reviews(self) -> None:
        connection = connect(self.database)
        connection.execute(
            """INSERT INTO observation_reviews(
            finding_key,observation_type,resolution,month,transaction_ids,active,
            reviewed_at,updated_at
            ) VALUES(?,?,?,?,?,1,?,?)""",
            (
                "UNUSUAL TRANSACTION:synthetic",
                "UNUSUAL TRANSACTION",
                "not_unusual",
                "2030-02",
                f"[{self.february_id}]",
                "2030-02-15T10:00:00",
                "2030-02-15T10:00:00",
            ),
        )
        connection.commit()
        connection.close()
        snapshot = load_observation_inputs(
            self.database,
            period="month",
            card="all",
            month="2030-02",
        )
        self.assertEqual(
            snapshot.reviewed_finding_keys,
            frozenset({"UNUSUAL TRANSACTION:synthetic"}),
        )

    def test_long_period_snapshot_uses_a_fixed_number_of_bulk_reads(self) -> None:
        connection = connect(self.database)
        import_id = connection.execute("SELECT id FROM imports LIMIT 1").fetchone()["id"]
        for number in range(3, 13):
            add_transaction(
                connection,
                import_id,
                key=f"month-{number}",
                merchant=f"Synthetic month {number}",
                amount=number * 10,
                category="Food",
                transaction_date=f"2030-{number:02d}-10",
                billing_month=f"2030-{number:02d}",
            )
        connection.commit()

        class CountingConnection:
            def __init__(self, wrapped):
                self.wrapped = wrapped
                self.statements = []

            def execute(self, sql, parameters=None):
                self.statements.append(sql)
                if parameters is None:
                    return self.wrapped.execute(sql)
                return self.wrapped.execute(sql, parameters)

            def rollback(self):
                self.wrapped.rollback()

        counted = CountingConnection(connection)

        @contextmanager
        def existing_connection(_database):
            yield counted

        with patch(
            "clearspend.observations.inputs.database_connection",
            existing_connection,
        ):
            snapshot = load_observation_inputs(
                self.database,
                period="all",
                card="all",
            )

        connection.close()
        self.assertEqual(len(snapshot.scope.recurring_months), 12)
        self.assertEqual(len(counted.statements), 7)
        self.assertEqual(
            sum("JOIN recurring_profile_members" in sql for sql in counted.statements),
            1,
        )


if __name__ == "__main__":
    unittest.main()
