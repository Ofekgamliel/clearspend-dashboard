from __future__ import annotations

import unittest
from contextlib import contextmanager
from unittest.mock import Mock, patch

from clearspend.database.postgresql_smoke import (
    run_category_smoke,
    run_dashboard_smoke,
    run_event_smoke,
    run_merchant_smoke,
    run_observation_review_smoke,
    run_observation_inputs_smoke,
    run_recurring_smoke,
    run_transaction_smoke,
)


@contextmanager
def yielding(value):
    yield value


class PostgreSQLSmokeTests(unittest.TestCase):
    def test_observation_inputs_smoke_cleans_up_synthetic_rows(self) -> None:
        insert_connection = Mock()
        insert_connection.execute.side_effect = [
            Mock(fetchone=Mock(return_value={"id": 161})),
            Mock(fetchone=Mock(return_value={"id": 171})),
            Mock(fetchone=Mock(return_value={"id": 172})),
            Mock(fetchone=Mock(return_value={"id": 181})),
            Mock(),
            Mock(),
            Mock(),
        ]
        cleanup_connection = Mock()
        snapshot = Mock()
        snapshot.scope.history_months = ("2000-01", "2000-02")
        snapshot.transactions_by_month = {"2000-01": (), "2000-02": ()}
        snapshot.income_visible = True
        snapshot.household_history = {"2000-02": {"income": 500.0}}
        snapshot.installments_by_month = {
            "2000-02": {"installment_billed": 40.0, "plans": ({"plan_id": "one"},)},
        }

        def load_result(pool, *, period, card, month):
            snapshot.reviewed_finding_keys = {
                insert_connection.execute.call_args_list[-1].args[1][0]
            }
            return snapshot

        with patch(
            "clearspend.database.postgresql_smoke.database_transaction",
            side_effect=[yielding(insert_connection), yielding(cleanup_connection)],
        ), patch(
            "clearspend.database.postgresql_smoke.load_observation_inputs",
            side_effect=load_result,
        ):
            result = run_observation_inputs_smoke(Mock())

        self.assertEqual(result, {
            "scope": True,
            "transactions": True,
            "income_visibility": True,
            "installments": True,
            "reviews": True,
        })
        self.assertEqual(cleanup_connection.execute.call_count, 5)

    def test_dashboard_smoke_cleans_up_synthetic_rows(self) -> None:
        insert_connection = Mock()
        insert_connection.execute.side_effect = [
            Mock(fetchone=Mock(return_value={"id": 131})),
            Mock(fetchone=Mock(return_value={"id": 141})),
            Mock(fetchone=Mock(return_value={"id": 142})),
            Mock(fetchone=Mock(return_value={"id": 143})),
            Mock(fetchone=Mock(return_value={"id": 151})),
            Mock(),
            Mock(),
        ]
        cleanup_connection = Mock()
        month_payload = {
            "metrics": {"spent": 150.0},
            "income_summary": {"income": 500.0, "remaining": 350.0},
            "cards": [{"amount": 150.0}],
            "available_months": ["2000-02", "2000-01"],
        }
        year_payload = {
            "trend": [
                {"bucket": "2000-01", "amount": 80.0, "income": 500.0},
                {"bucket": "2000-02", "amount": 150.0, "income": 500.0},
            ],
        }
        with patch(
            "clearspend.database.postgresql_smoke.database_transaction",
            side_effect=[yielding(insert_connection), yielding(cleanup_connection)],
        ), patch(
            "clearspend.database.postgresql_smoke.dashboard_payload",
            side_effect=[month_payload, year_payload],
        ):
            result = run_dashboard_smoke(Mock())

        self.assertEqual(result, {
            "spending": True,
            "income": True,
            "balance": True,
            "cards": True,
            "coverage": True,
            "trend": True,
        })
        self.assertEqual(cleanup_connection.execute.call_count, 4)

    def test_category_smoke_cleans_up_synthetic_rows(self) -> None:
        insert_connection = Mock()
        insert_connection.execute.side_effect = [
            Mock(fetchone=Mock(return_value={"id": 111})),
            Mock(fetchone=Mock(return_value={"id": 121})),
            Mock(fetchone=Mock(return_value={"id": 122})),
            Mock(fetchone=Mock(return_value={"id": 123})),
            Mock(),
            Mock(),
        ]
        cleanup_connection = Mock()
        payloads = [
            {
                "total": 200.0,
                "categories": [
                    {"category": "Category Alpha", "change_percent": 50},
                    {"category": "Category Beta", "comparison": "new"},
                ],
            },
            {"total": 150.0, "categories": []},
            {"total": 150.0, "categories": []},
        ]
        with patch(
            "clearspend.database.postgresql_smoke.database_transaction",
            side_effect=[yielding(insert_connection), yielding(cleanup_connection)],
        ), patch(
            "clearspend.database.postgresql_smoke.categories_payload",
            side_effect=payloads,
        ):
            result = run_category_smoke(Mock())

        self.assertEqual(result, {
            "totals": True,
            "comparison": True,
            "event_scope": True,
            "card_scope": True,
        })
        self.assertEqual(cleanup_connection.execute.call_count, 4)

    def test_recurring_smoke_cleans_up_synthetic_rows(self) -> None:
        insert_connection = Mock()
        insert_connection.execute.side_effect = [
            Mock(fetchone=Mock(return_value={"id": 91})),
            Mock(fetchone=Mock(return_value={"id": 101})),
            Mock(fetchone=Mock(return_value={"id": 102})),
            Mock(fetchone=Mock(return_value={"id": 103})),
            Mock(),
            Mock(),
        ]
        cleanup_connection = Mock()
        selected_alias: list[str] = []

        def manage_result(pool, group_id, verdict, *args):
            if verdict == "recurring":
                selected_alias.append(args[4][0])
                return {"verdict": "recurring"}
            return {"verdict": "not_recurring", "included_aliases": list(selected_alias)}

        with patch(
            "clearspend.database.postgresql_smoke.database_transaction",
            side_effect=[yielding(insert_connection), yielding(cleanup_connection)],
        ), patch(
            "clearspend.database.postgresql_smoke.manage_recurring_profile",
            side_effect=manage_result,
        ) as manage, patch(
            "clearspend.database.postgresql_smoke.recurring_payload",
        ) as payload, patch(
            "clearspend.database.postgresql_smoke.save_recurring_profile",
            return_value={"end_month": "2000-02"},
        ):
            def recurring_result(pool, period, card, month):
                selected = selected_alias[0]
                group_id = manage.call_args_list[0].args[1]
                return {
                    "series": [{
                        "canonical_group_id": group_id,
                        "source_aliases": [selected.title()],
                    }],
                    "metrics": {"recurring_billed": 55.0},
                }

            payload.side_effect = recurring_result
            result = run_recurring_smoke(Mock())

        self.assertEqual(result, {
            "profile": True,
            "selected_alias": True,
            "read": True,
            "lifecycle": True,
            "membership_preserved": True,
        })
        self.assertEqual(cleanup_connection.execute.call_count, 5)

    def test_event_smoke_cleans_up_synthetic_rows(self) -> None:
        insert_connection = Mock()
        insert_connection.execute.side_effect = [
            Mock(fetchone=Mock(return_value={"id": 71})),
            Mock(fetchone=Mock(return_value={"id": 81})),
        ]
        membership_connection = Mock()
        membership_connection.execute.return_value.fetchone.return_value = {"count": 1}
        cleanup_connection = Mock()
        with patch(
            "clearspend.database.postgresql_smoke.database_transaction",
            side_effect=[
                yielding(insert_connection),
                yielding(membership_connection),
                yielding(cleanup_connection),
            ],
        ), patch(
            "clearspend.database.postgresql_smoke.create_event",
            return_value={"status": "created", "event": {"id": "event-synthetic"}},
        ), patch(
            "clearspend.database.postgresql_smoke.save_transaction_event",
            side_effect=[{"status": "assigned"}, {"status": "unassigned"}],
        ), patch(
            "clearspend.database.postgresql_smoke.events_payload",
            return_value={"events": [{"id": "event-synthetic", "transaction_count": 1}]},
        ), patch(
            "clearspend.database.postgresql_smoke.save_event_settings",
        ):
            result = run_event_smoke(Mock())

        self.assertEqual(result, {
            "created": True,
            "assigned": True,
            "read": True,
            "membership_preserved": True,
            "unassigned": True,
        })
        self.assertEqual(cleanup_connection.execute.call_count, 4)

    def test_merchant_smoke_cleans_up_synthetic_rows(self) -> None:
        insert_connection = Mock()
        insert_connection.execute.side_effect = [
            Mock(fetchone=Mock(return_value={"id": 51})),
            Mock(fetchone=Mock(return_value={"id": 61})),
            Mock(fetchone=Mock(return_value={"id": 62})),
            Mock(),
            Mock(),
            Mock(),
        ]
        future_connection = Mock()
        future_connection.execute.side_effect = [
            Mock(fetchone=Mock(return_value={"id": 63})),
            Mock(fetchone=Mock(return_value={
                "user_category": "Synthetic category",
                "user_subcategory": "Exact alias",
            })),
        ]
        cleanup_connection = Mock()
        save = Mock(return_value={"transactions_updated": 1})
        with patch(
            "clearspend.database.postgresql_smoke.database_transaction",
            side_effect=[
                yielding(insert_connection),
                yielding(future_connection),
                yielding(cleanup_connection),
            ],
        ), patch(
            "clearspend.database.postgresql_smoke.save_merchant",
            new=save,
        ), patch(
            "clearspend.database.postgresql_smoke.merchants_payload",
            return_value={"merchants": [{
                "canonical_group_id": "placeholder",
                "display_name": "Synthetic Group",
                "transactions": 3,
            }]},
        ) as payload:
            def matching_payload(pool):
                return {"merchants": [{
                    "canonical_group_id": save.call_args.args[1],
                    "display_name": "Synthetic Group",
                    "transactions": 3,
                }]}

            payload.side_effect = matching_payload
            with patch(
                "clearspend.database.postgresql_smoke.mapping_payload",
                return_value={
                    "recent_imports": [{"id": 51, "coverage": [{"card_last4": "0000"}]}],
                },
            ):
                result = run_merchant_smoke(Mock())

        self.assertEqual(result, {
            "identity": True,
            "historical_category": True,
            "future_category": True,
            "independent_aliases": True,
            "mapping_context": True,
        })
        self.assertEqual(cleanup_connection.execute.call_count, 6)

    def test_observation_review_smoke_cleans_up_synthetic_rows(self) -> None:
        insert_connection = Mock()
        insert_connection.execute.side_effect = [
            Mock(fetchone=Mock(return_value={"id": 11})),
            Mock(fetchone=Mock(return_value={"id": 21})),
            Mock(fetchone=Mock(return_value={"id": 22})),
        ]
        cleanup_connection = Mock()
        save_results = [
            {"status": "reviewed"},
            {"status": "restored", "changed": True},
        ]
        with patch(
            "clearspend.database.postgresql_smoke.database_transaction",
            side_effect=[yielding(insert_connection), yielding(cleanup_connection)],
        ), patch(
            "clearspend.database.postgresql_smoke.save_observation_review",
            side_effect=save_results,
        ) as save, patch(
            "clearspend.database.postgresql_smoke.observation_reviews_payload",
            return_value={"reviews": [{"finding_key": "placeholder"}]},
        ) as payload:
            def matching_payload(pool):
                finding_key = save.call_args_list[0].args[1]
                return {"reviews": [{"finding_key": finding_key}]}

            payload.side_effect = matching_payload
            result = run_observation_review_smoke(Mock())

        self.assertEqual(result, {"saved": True, "read": True, "undone": True})
        self.assertEqual(save.call_count, 2)
        self.assertEqual(cleanup_connection.execute.call_count, 3)
        cleanup_sql = [call.args[0] for call in cleanup_connection.execute.call_args_list]
        self.assertTrue(cleanup_sql[0].startswith("DELETE FROM observation_reviews"))
        self.assertTrue(cleanup_sql[1].startswith("DELETE FROM transactions"))
        self.assertTrue(cleanup_sql[2].startswith("DELETE FROM imports"))

    def test_transaction_smoke_cleans_up_synthetic_rows(self) -> None:
        insert_connection = Mock()
        insert_connection.execute.side_effect = [
            Mock(fetchone=Mock(return_value={"id": 31})),
            Mock(fetchone=Mock(return_value={"id": 41})),
        ]
        cleanup_connection = Mock()
        with patch(
            "clearspend.database.postgresql_smoke.database_transaction",
            side_effect=[yielding(insert_connection), yielding(cleanup_connection)],
        ), patch(
            "clearspend.database.postgresql_smoke.save_transaction_category",
            return_value={"status": "saved"},
        ), patch(
            "clearspend.database.postgresql_smoke.save_transaction_adjustment",
            return_value={"status": "saved"},
        ), patch(
            "clearspend.database.postgresql_smoke.transactions_payload",
            return_value={
                "transactions": [
                    {
                        "id": 41,
                        "category": "Synthetic override",
                        "personal_amount": 75.0,
                    }
                ]
            },
        ):
            result = run_transaction_smoke(Mock())

        self.assertEqual(
            result,
            {
                "category": True,
                "adjustment": True,
                "search": True,
                "personal_amount": True,
            },
        )
        self.assertEqual(cleanup_connection.execute.call_count, 4)


if __name__ == "__main__":
    unittest.main()
