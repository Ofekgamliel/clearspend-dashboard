from __future__ import annotations

import json
import tempfile
import unittest
from io import BytesIO
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from clearspend.http.handler import ClearSpendHandler
from tests.synthetic.support import create_database


class InMemorySocket:
    def __init__(self, request: bytes):
        self.request = BytesIO(request)
        self.response = BytesIO()

    def makefile(self, mode: str, *args, **kwargs):
        return self.request if "r" in mode else self.response

    def sendall(self, data: bytes) -> None:
        self.response.write(data)


class HttpHandlerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        root = Path(self.temporary_directory.name)
        self.database = root / "synthetic.db"
        create_database(self.database)
        self.static_dir = root / "static"
        self.static_dir.mkdir()
        (self.static_dir / "index.html").write_text(
            "<main>Synthetic dashboard</main>",
            encoding="utf-8",
        )
        (self.static_dir / "app.css").write_text(
            "main { color: navy; }",
            encoding="utf-8",
        )
        self.server = SimpleNamespace(
            database=self.database,
            static_dir=self.static_dir,
            staged_imports={},
            server_name="127.0.0.1",
            server_port=8765,
        )

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    def request(
        self,
        method: str,
        path: str,
        body: bytes | None = None,
        headers: dict[str, str] | None = None,
    ) -> tuple[int, dict[str, str], bytes]:
        request_headers = {"Host": "127.0.0.1", **(headers or {})}
        if body is not None:
            request_headers["Content-Length"] = str(len(body))
        raw_headers = "".join(
            f"{key}: {value}\r\n" for key, value in request_headers.items()
        )
        raw_request = (
            f"{method} {path} HTTP/1.0\r\n{raw_headers}\r\n".encode("ascii")
            + (body or b"")
        )
        connection = InMemorySocket(raw_request)
        with patch("builtins.print"):
            ClearSpendHandler(connection, ("127.0.0.1", 12345), self.server)
        head, response_body = connection.response.getvalue().split(b"\r\n\r\n", 1)
        lines = head.decode("iso-8859-1").split("\r\n")
        status = int(lines[0].split(" ", 2)[1])
        response_headers = {
            key.lower(): value.strip()
            for key, value in (line.split(":", 1) for line in lines[1:])
        }
        return status, response_headers, response_body

    def test_health_response_uses_json_contract_and_no_store(self) -> None:
        status, headers, body = self.request("GET", "/api/health")

        self.assertEqual(status, 200)
        self.assertEqual(headers["cache-control"], "no-store")
        self.assertEqual(headers["content-type"], "application/json; charset=utf-8")
        self.assertEqual(
            json.loads(body),
            {"status": "ok", "mode": "local", "database": True},
        )

    def test_static_assets_and_single_page_fallback_are_preserved(self) -> None:
        asset_status, asset_headers, asset_body = self.request("GET", "/app.css")
        fallback_status, _, fallback_body = self.request("GET", "/events/review")

        self.assertEqual(asset_status, 200)
        self.assertEqual(asset_headers["content-type"], "text/css; charset=utf-8")
        self.assertEqual(asset_body, b"main { color: navy; }")
        self.assertEqual(fallback_status, 200)
        self.assertEqual(fallback_body, b"<main>Synthetic dashboard</main>")

    def test_static_path_traversal_is_forbidden(self) -> None:
        status, _, _ = self.request("GET", "/../private.txt")

        self.assertEqual(status, 403)

    def test_malformed_json_and_unknown_post_keep_existing_statuses(self) -> None:
        invalid_status, invalid_headers, invalid_body = self.request(
            "POST",
            "/api/mapping",
            body=b"{invalid",
            headers={"Content-Type": "application/json"},
        )
        missing_status, _, _ = self.request("POST", "/api/not-real")

        self.assertEqual(invalid_status, 400)
        self.assertEqual(
            invalid_headers["content-type"],
            "application/json; charset=utf-8",
        )
        self.assertIn("error", json.loads(invalid_body))
        self.assertEqual(missing_status, 404)


if __name__ == "__main__":
    unittest.main()
