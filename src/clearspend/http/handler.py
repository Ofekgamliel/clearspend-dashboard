from __future__ import annotations

import json
import mimetypes
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler
from pathlib import Path
from typing import Protocol, cast
from urllib.parse import parse_qs, urlparse

from clearspend.http.api import (
    JSON_GET_PATHS,
    JSON_POST_PATHS,
    dispatch_json_get,
    dispatch_json_post,
)
from clearspend.http.imports import commit_staged_import, process_import_uploads
from clearspend.http.json_body import read_json_object
from clearspend.http.multipart import parse_multipart_files


class ClearSpendApplication(Protocol):
    database: Path
    static_dir: Path
    staged_imports: dict[str, dict]


class ClearSpendHandler(BaseHTTPRequestHandler):
    server_version = "ClearSpend/0.1"

    @property
    def app(self) -> ClearSpendApplication:
        return cast(ClearSpendApplication, self.server)

    def send_json(self, payload: object, status: int = 200) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path in JSON_GET_PATHS:
            try:
                result, status = dispatch_json_get(
                    self.app.database,
                    parsed.path,
                    parse_qs(parsed.query),
                )
                self.send_json(result, status)
            except ValueError as error:
                self.send_json({"error": str(error)}, 400)
            except Exception as error:
                self.send_json({"error": str(error)}, 500)
            return
        self.serve_static(parsed.path)

    def do_POST(self) -> None:
        parsed_path = urlparse(self.path).path
        if parsed_path in JSON_POST_PATHS:
            try:
                payload = read_json_object(
                    self.rfile,
                    self.headers.get("Content-Length"),
                )
                result, status = dispatch_json_post(
                    self.app.database,
                    parsed_path,
                    payload,
                )
                self.send_json(result, status)
            except (TypeError, ValueError, json.JSONDecodeError) as error:
                self.send_json({"error": str(error)}, 400)
            except Exception as error:
                self.send_json({"error": str(error)}, 500)
            return
        if parsed_path == "/api/import/commit":
            try:
                payload = read_json_object(
                    self.rfile,
                    self.headers.get("Content-Length"),
                    max_bytes=8 * 1024 * 1024,
                )
                result, status = commit_staged_import(
                    self.app.database,
                    self.app.staged_imports,
                    payload,
                )
                self.send_json(result, status)
            except (ValueError, json.JSONDecodeError) as error:
                self.send_json({"error": str(error)}, 400)
            except Exception as error:
                self.send_json({"error": str(error)}, 500)
            return
        if parsed_path not in {"/api/import", "/api/import/analyze"}:
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        content_type = self.headers.get("Content-Type", "")
        if not content_type.startswith("multipart/form-data"):
            self.send_json({"error": "Expected multipart file upload"}, 400)
            return
        try:
            content_length = int(self.headers.get("Content-Length", "0"))
            items = parse_multipart_files(
                self.rfile,
                content_type,
                content_length,
            )
        except (TypeError, ValueError) as error:
            self.send_json({"error": str(error)}, 400)
            return
        try:
            result, status = process_import_uploads(
                self.app.database,
                self.app.staged_imports,
                items,
                staged=parsed_path == "/api/import/analyze",
            )
            self.send_json(result, status)
        except Exception as error:
            self.send_json({"error": str(error)}, 400)

    def serve_static(self, requested_path: str) -> None:
        relative = requested_path.lstrip("/") or "index.html"
        candidate = (self.app.static_dir / relative).resolve()
        static_root = self.app.static_dir.resolve()
        if static_root not in candidate.parents and candidate != static_root:
            self.send_error(HTTPStatus.FORBIDDEN)
            return
        if candidate.is_dir():
            candidate /= "index.html"
        if not candidate.is_file():
            candidate = self.app.static_dir / "index.html"
        body = candidate.read_bytes()
        content_type = mimetypes.guess_type(candidate.name)[0] or "application/octet-stream"
        self.send_response(HTTPStatus.OK)
        self.send_header(
            "Content-Type",
            f"{content_type}; charset=utf-8"
            if content_type.startswith("text/")
            else content_type,
        )
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args: object) -> None:
        print(f"[{self.log_date_time_string()}] {format % args}")
