from __future__ import annotations

import unittest
from io import BytesIO

from clearspend.http.multipart import parse_multipart_files


def multipart_body(boundary: str, parts: list[tuple[str, str, bytes]]) -> bytes:
    body = bytearray()
    for field_name, filename, payload in parts:
        body.extend(f"--{boundary}\r\n".encode())
        body.extend(
            f'Content-Disposition: form-data; name="{field_name}"; filename="{filename}"\r\n'.encode()
        )
        body.extend(b"Content-Type: application/octet-stream\r\n\r\n")
        body.extend(payload)
        body.extend(b"\r\n")
    body.extend(f"--{boundary}--\r\n".encode())
    return bytes(body)


class MultipartTests(unittest.TestCase):
    def test_multiple_binary_files_are_decoded_in_order(self) -> None:
        boundary = "synthetic-boundary"
        body = multipart_body(boundary, [
            ("files", "first.xlsx", b"PK\x00synthetic-xlsx"),
            ("files", "second.pdf", b"%PDF-1.7\x00synthetic-pdf"),
        ])

        uploads = parse_multipart_files(
            BytesIO(body), f'multipart/form-data; boundary="{boundary}"', len(body)
        )

        self.assertEqual([item.filename for item in uploads], ["first.xlsx", "second.pdf"])
        self.assertEqual(uploads[0].file.read(), b"PK\x00synthetic-xlsx")
        self.assertEqual(uploads[1].file.read(), b"%PDF-1.7\x00synthetic-pdf")

    def test_unrelated_form_fields_are_ignored(self) -> None:
        boundary = "synthetic-boundary"
        body = multipart_body(boundary, [
            ("metadata", "ignored.txt", b"ignored"),
            ("files", "statement.xlsx", b"accepted"),
        ])

        uploads = parse_multipart_files(
            BytesIO(body), f"multipart/form-data; boundary={boundary}", len(body)
        )

        self.assertEqual(len(uploads), 1)
        self.assertEqual(uploads[0].filename, "statement.xlsx")

    def test_missing_boundary_empty_body_and_size_limit_are_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "boundary"):
            parse_multipart_files(BytesIO(b"body"), "multipart/form-data", 4)
        with self.assertRaisesRegex(ValueError, "empty"):
            parse_multipart_files(
                BytesIO(), "multipart/form-data; boundary=synthetic", 0
            )
        with self.assertRaisesRegex(ValueError, "limit"):
            parse_multipart_files(
                BytesIO(b"12345"), "multipart/form-data; boundary=synthetic", 5,
                max_bytes=4,
            )

    def test_truncated_request_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "before all bytes"):
            parse_multipart_files(
                BytesIO(b"short"), "multipart/form-data; boundary=synthetic", 10
            )


if __name__ == "__main__":
    unittest.main()
