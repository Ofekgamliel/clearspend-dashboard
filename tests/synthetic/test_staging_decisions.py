from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from clearspend.staging.decisions import (
    apply_permanent_merchant_decisions,
    reviewed_duplicate_matches,
)
from tests.synthetic.support import connect, create_database


class StagingDecisionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.database = Path(self.temporary_directory.name) / "synthetic.db"
        create_database(self.database)

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    def test_reviewed_duplicate_skip_builds_import_match_and_import_action_does_not(self) -> None:
        analysis = {"possible_duplicates": [
            {
                "candidate_id": "candidate-skip",
                "file_index": 2,
                "transaction_key": "incoming-skip",
                "matched_transaction_ids": [17],
            },
            {
                "candidate_id": "candidate-import",
                "file_index": 1,
                "transaction_key": "incoming-import",
                "matched_transaction_ids": [19],
            },
        ]}

        matches = reviewed_duplicate_matches(analysis, [
            {"candidate_id": "candidate-skip", "action": "skip"},
            {"candidate_id": "candidate-import", "action": "import"},
        ])

        self.assertEqual(matches, {2: {"incoming-skip": 17}})

    def test_duplicate_review_requires_current_decision_for_every_candidate(self) -> None:
        analysis = {"possible_duplicates": [{
            "candidate_id": "candidate-1",
            "file_index": 0,
            "transaction_key": "incoming",
            "matched_transaction_ids": [1],
        }]}

        with self.assertRaisesRegex(ValueError, "must be reviewed"):
            reviewed_duplicate_matches(analysis, [])
        with self.assertRaisesRegex(ValueError, "invalid or no longer current"):
            reviewed_duplicate_matches(
                analysis,
                [{"candidate_id": "candidate-1", "action": "unexpected"}],
            )

    def test_exact_merchant_decision_persists_category_and_custom_display_identity(self) -> None:
        connection = connect(self.database)
        apply_permanent_merchant_decisions(
            connection,
            {"synthetic merchant": {
                "resolution": "create",
                "scope": "exact",
                "category": "Synthetic Category",
                "display_name": "Synthetic Display",
            }},
            "2030-01-15T10:00:00",
        )
        connection.commit()
        mapping = connection.execute(
            "SELECT category FROM merchant_mappings WHERE merchant_normalized=?",
            ("synthetic merchant",),
        ).fetchone()
        display = connection.execute(
            """SELECT canonical_group_id,display_name FROM merchant_display_mappings
            WHERE merchant_normalized=?""",
            ("synthetic merchant",),
        ).fetchone()
        connection.close()

        self.assertEqual(mapping["category"], "Synthetic Category")
        self.assertEqual(display["display_name"], "Synthetic Display")
        self.assertTrue(display["canonical_group_id"].startswith("custom:"))


if __name__ == "__main__":
    unittest.main()
