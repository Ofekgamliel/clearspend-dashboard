from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from clearspend.staging.service import commit_staged_batch
from tests.synthetic.support import add_import, add_transaction, connect, create_database


class StagingServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.database = Path(self.temporary_directory.name) / "synthetic.db"
        create_database(self.database)
        connection = connect(self.database)
        import_id = add_import(connection)
        add_transaction(
            connection, import_id, key="existing", merchant="Synthetic Existing",
            amount=25, category="Household",
        )
        connection.commit()
        connection.close()

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    def database_counts(self) -> tuple[int, int, int]:
        connection = connect(self.database)
        try:
            return (
                connection.execute("SELECT COUNT(*) FROM transactions").fetchone()[0],
                connection.execute("SELECT COUNT(*) FROM merchant_mappings").fetchone()[0],
                connection.execute("SELECT COUNT(*) FROM merchant_display_mappings").fetchone()[0],
            )
        finally:
            connection.close()

    def test_unreviewed_possible_duplicate_is_rejected_without_database_changes(self) -> None:
        before = self.database_counts()
        analysis = {
            "possible_duplicates": [{
                "candidate_id": "candidate-1",
                "file_index": 0,
                "transaction_key": "incoming-key",
                "matched_transaction_ids": [1],
            }],
            "merchants": [],
            "pending_transactions": [],
            "files": [],
        }

        with self.assertRaisesRegex(ValueError, "must be reviewed"):
            commit_staged_batch(
                self.database, {"uploads": []}, [], [], analysis
            )

        self.assertEqual(self.database_counts(), before)
        backups = list((self.database.parent / "backups").glob("clearspend-before-import-*.db"))
        self.assertEqual(len(backups), 1)

    def test_invalid_link_decision_rolls_back_mapping_changes(self) -> None:
        before = self.database_counts()
        analysis = {
            "possible_duplicates": [],
            "merchants": [],
            "pending_transactions": [],
            "files": [],
        }
        decisions = [{
            "merchant_normalized": "synthetic incoming",
            "resolution": "link",
            "scope": "batch",
            "category": "Travel",
            "display_name": "Synthetic Existing",
            "canonical_group_id": "synthetic existing",
        }]

        with self.assertRaisesRegex(ValueError, "permanent exact-name scope"):
            commit_staged_batch(
                self.database, {"uploads": []}, decisions, [], analysis
            )

        self.assertEqual(self.database_counts(), before)


if __name__ == "__main__":
    unittest.main()
