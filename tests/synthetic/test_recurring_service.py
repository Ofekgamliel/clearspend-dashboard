from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from clearspend.recurring.service import manage_recurring_profile, save_recurring_profile
from tests.synthetic.support import add_import, add_transaction, connect, create_database


class RecurringServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.database = Path(self.temporary_directory.name) / "synthetic.db"
        create_database(self.database)
        connection = connect(self.database)
        try:
            import_id = add_import(connection)
            self.aliases = ["synthetic mobile one", "synthetic mobile two"]
            for index, alias in enumerate(self.aliases):
                add_transaction(
                    connection, import_id, key=f"recurring-{index}", merchant=alias.title(),
                    amount=50 + index, category="Communications",
                )
                connection.execute(
                    """INSERT INTO merchant_display_mappings(
                    merchant_normalized,canonical_group_id,display_name,updated_at
                    ) VALUES(?,'synthetic-mobile','Synthetic Mobile','2030-01-01')""",
                    (alias,),
                )
            connection.commit()
        finally:
            connection.close()

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    def test_manage_profile_persists_only_selected_alias(self) -> None:
        profile = manage_recurring_profile(
            self.database, "synthetic-mobile", "recurring", "Fixed recurring", "Monthly",
            "active", "", [self.aliases[0]],
        )

        self.assertEqual(profile["included_aliases"], [self.aliases[0]])
        connection = connect(self.database)
        try:
            membership = dict(connection.execute(
                """SELECT merchant_normalized,included FROM recurring_profile_members
                WHERE canonical_group_id='synthetic-mobile'"""
            ).fetchall())
        finally:
            connection.close()
        self.assertEqual(membership, {self.aliases[0]: 1, self.aliases[1]: 0})

    def test_lifecycle_edit_persists_end_month_and_clears_it_when_active(self) -> None:
        manage_recurring_profile(
            self.database, "synthetic-mobile", "recurring", "Fixed recurring", "Monthly",
            "active", "",
        )

        ended = save_recurring_profile(
            self.database, "synthetic-mobile", "Fixed recurring", "Monthly", "ended", "2030-03"
        )
        self.assertEqual(ended["end_month"], "2030-03")
        active = save_recurring_profile(
            self.database, "synthetic-mobile", "Usage-based recurring", "Monthly", "active", "2030-03"
        )
        self.assertIsNone(active["end_month"])

    def test_unknown_alias_is_rejected_without_creating_profile(self) -> None:
        with self.assertRaisesRegex(ValueError, "does not belong"):
            manage_recurring_profile(
                self.database, "synthetic-mobile", "recurring", "Fixed recurring", "Monthly",
                "active", "", ["unrelated alias"],
            )
        connection = connect(self.database)
        try:
            count = connection.execute("SELECT COUNT(*) FROM recurring_profiles").fetchone()[0]
        finally:
            connection.close()
        self.assertEqual(count, 0)
