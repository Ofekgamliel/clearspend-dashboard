from __future__ import annotations

import json
import unittest
from io import BytesIO

from clearspend.http.json_body import read_json_object


class JsonBodyTests(unittest.TestCase):
    def test_object_and_empty_body_are_supported(self) -> None:
        body = json.dumps({"name": "Synthetic", "count": 2}).encode()

        self.assertEqual(
            read_json_object(BytesIO(body), str(len(body))),
            {"name": "Synthetic", "count": 2},
        )
        self.assertEqual(read_json_object(BytesIO(), None), {})

    def test_invalid_length_and_oversized_body_are_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "integer"):
            read_json_object(BytesIO(), "invalid")
        with self.assertRaisesRegex(ValueError, "negative"):
            read_json_object(BytesIO(), -1)
        with self.assertRaisesRegex(ValueError, "limit"):
            read_json_object(BytesIO(b"12345"), 5, max_bytes=4)

    def test_truncated_and_malformed_json_are_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "before all bytes"):
            read_json_object(BytesIO(b"{}"), 3)
        with self.assertRaises(json.JSONDecodeError):
            read_json_object(BytesIO(b"{"), 1)

    def test_non_object_json_is_rejected(self) -> None:
        body = b'["synthetic"]'

        with self.assertRaisesRegex(ValueError, "must be an object"):
            read_json_object(BytesIO(body), len(body))


if __name__ == "__main__":
    unittest.main()
