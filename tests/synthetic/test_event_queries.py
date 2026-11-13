from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from clearspend.events.queries import events_payload
from clearspend.events.service import create_event, save_transaction_event
from tests.synthetic.support import add_import, add_transaction, connect, create_database


class EventQueryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.database = Path(self.temporary_directory.name) / "synthetic.db"
        create_database(self.database)

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    def test_event_payload_separates_selected_month_from_lifetime_membership(self) -> None:
        event = create_event(
            self.database, "Synthetic journey", "trip", "2030-01-30", "2030-02-02",
            "", "completed",
        )["event"]
        connection = connect(self.database)
        try:
            import_id = add_import(connection)
            january_id = add_transaction(
                connection, import_id, key="january-event", merchant="Synthetic Rail",
                amount=40, category="Travel", transaction_date="2030-01-31", billing_month="2030-01",
            )
            february_id = add_transaction(
                connection, import_id, key="february-event", merchant="Synthetic Hotel",
                amount=160, category="Accommodation", transaction_date="2030-02-01",
                billing_month="2030-02", card_last4="0002",
            )
            connection.commit()
        finally:
            connection.close()
        save_transaction_event(self.database, january_id, event["id"])
        save_transaction_event(self.database, february_id, event["id"])

        item = events_payload(self.database, "month", "all", "2030-01")["events"][0]

        self.assertEqual(item["transaction_count"], 1)
        self.assertEqual(item["amount"], 40)
        self.assertEqual(item["total_transaction_count"], 2)
        self.assertEqual(item["total_amount"], 200)
        self.assertEqual(item["category_count"], 2)
        self.assertEqual(item["card_count"], 2)

    def test_card_selection_hides_event_without_matching_membership(self) -> None:
        event = create_event(
            self.database, "Synthetic day", "other", "2030-01-10", "2030-01-10",
            "", "completed",
        )["event"]
        connection = connect(self.database)
        try:
            import_id = add_import(connection)
            transaction_id = add_transaction(
                connection, import_id, key="selected-card-event", merchant="Synthetic Venue",
                amount=25, category="Leisure", card_last4="0001",
            )
            connection.commit()
        finally:
            connection.close()
        save_transaction_event(self.database, transaction_id, event["id"])

        payload = events_payload(self.database, "month", "synthetic:9999", "2030-01")
        self.assertEqual(payload["events"], [])
        self.assertEqual(len(payload["available_events"]), 1)
