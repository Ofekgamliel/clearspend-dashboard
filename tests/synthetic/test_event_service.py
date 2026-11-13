from __future__ import annotations

import sqlite3
import tempfile
import unittest
from pathlib import Path

from clearspend.events.service import create_event, save_event_settings, save_transaction_event
from tests.synthetic.support import add_import, add_transaction, connect, create_database


class EventServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.database = Path(self.temporary_directory.name) / "synthetic.db"
        create_database(self.database)

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    def create_synthetic_event(self) -> dict:
        return create_event(
            self.database, "Synthetic event", "trip", "2030-02-01", "2030-02-03",
            "500", "planned",
        )["event"]

    def test_create_and_edit_event_persist_normalized_settings(self) -> None:
        event = self.create_synthetic_event()

        result = save_event_settings(
            self.database, event["id"], " Synthetic work visit ", "business_trip",
            "2030-02-02", "2030-02-04", "725.456", "completed", " Test City ",
        )

        self.assertEqual(result["status"], "updated")
        self.assertEqual(result["event"]["name"], "Synthetic work visit")
        self.assertEqual(result["event"]["destination"], "Test City")
        # The existing API exposes the SQLite TEXT value; preserve that contract
        # until a separately reviewed response-schema change.
        self.assertEqual(result["event"]["budget"], "725.46")
        connection = sqlite3.connect(self.database)
        try:
            persisted = connection.execute(
                "SELECT name,event_type,destination,status FROM events WHERE id=?", (event["id"],)
            ).fetchone()
        finally:
            connection.close()
        self.assertEqual(
            persisted, ("Synthetic work visit", "business_trip", "Test City", "completed")
        )

    def test_assignment_and_unassignment_are_persisted(self) -> None:
        event = self.create_synthetic_event()
        connection = connect(self.database)
        try:
            import_id = add_import(connection)
            transaction_id = add_transaction(
                connection, import_id, key="event-member", merchant="Synthetic Venue",
                amount=80, category="Leisure",
            )
            connection.commit()
        finally:
            connection.close()

        assigned = save_transaction_event(self.database, transaction_id, event["id"])
        self.assertEqual(assigned["status"], "assigned")
        self.assertEqual(assigned["event_name"], "Synthetic event")

        unassigned = save_transaction_event(self.database, transaction_id, "")
        self.assertEqual(unassigned["status"], "unassigned")
        connection = sqlite3.connect(self.database)
        try:
            membership_count = connection.execute(
                "SELECT COUNT(*) FROM event_transactions WHERE transaction_id=?", (transaction_id,)
            ).fetchone()[0]
        finally:
            connection.close()
        self.assertEqual(membership_count, 0)

    def test_cancelled_event_cannot_receive_new_assignment(self) -> None:
        event = self.create_synthetic_event()
        save_event_settings(
            self.database, event["id"], event["name"], event["event_type"],
            event["start_date"], event["end_date"], event["budget"], "cancelled",
        )
        connection = connect(self.database)
        try:
            import_id = add_import(connection)
            transaction_id = add_transaction(
                connection, import_id, key="cancelled-member", merchant="Synthetic Shop",
                amount=25, category="Shopping",
            )
            connection.commit()
        finally:
            connection.close()

        with self.assertRaisesRegex(ValueError, "Event not found"):
            save_transaction_event(self.database, transaction_id, event["id"])
