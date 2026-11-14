from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from clearspend.observations.queries import observation_reviews_payload
from clearspend.observations.service import save_observation_review
from tests.synthetic.support import add_import, add_transaction, connect, create_database


class ObservationReviewTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.database = Path(self.temporary_directory.name) / "synthetic.db"
        create_database(self.database)
        connection = connect(self.database)
        try:
            import_id = add_import(connection)
            self.transaction_ids = [
                add_transaction(
                    connection, import_id, key=f"duplicate-{index}",
                    merchant="Synthetic Store", amount=25, category="Shopping",
                )
                for index in range(2)
            ]
            connection.commit()
        finally:
            connection.close()

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    def test_review_is_persisted_with_sorted_unique_transaction_ids(self) -> None:
        finding_key = "POSSIBLE DUPLICATE:synthetic-group"
        result = save_observation_review(
            self.database, finding_key, "possible duplicate", "not_duplicate", "2030-01",
            [self.transaction_ids[1], self.transaction_ids[0], self.transaction_ids[1]],
            merchant_label="Synthetic Store",
        )

        self.assertEqual(result["status"], "reviewed")
        review = observation_reviews_payload(self.database)["reviews"][0]
        self.assertEqual(review["finding_key"], finding_key)
        self.assertEqual(review["transaction_ids"], sorted(self.transaction_ids))
        self.assertEqual(review["merchant_label"], "Synthetic Store")

    def test_remove_hides_review_and_saving_again_restores_it(self) -> None:
        finding_key = "UNUSUAL TRANSACTION:synthetic-one"
        arguments = (
            self.database, finding_key, "UNUSUAL TRANSACTION", "not_unusual", "2030-01",
            [self.transaction_ids[0]],
        )
        save_observation_review(*arguments)

        removed = save_observation_review(*arguments, remove=True)
        self.assertEqual(removed, {"status": "restored", "finding_key": finding_key, "changed": True})
        self.assertEqual(observation_reviews_payload(self.database)["reviews"], [])

        save_observation_review(*arguments)
        self.assertEqual(len(observation_reviews_payload(self.database)["reviews"]), 1)

    def test_invalid_review_does_not_write_state(self) -> None:
        with self.assertRaisesRegex(ValueError, "at least two transactions"):
            save_observation_review(
                self.database, "POSSIBLE DUPLICATE:too-small", "POSSIBLE DUPLICATE",
                "not_duplicate", "2030-01", [self.transaction_ids[0]],
            )
        self.assertEqual(observation_reviews_payload(self.database)["reviews"], [])
