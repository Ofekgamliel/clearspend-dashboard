from __future__ import annotations

from dataclasses import dataclass
from email import policy
from email.parser import BytesParser
from io import BytesIO
from typing import BinaryIO


MAX_UPLOAD_REQUEST_BYTES = 128 * 1024 * 1024


@dataclass(frozen=True)
class UploadedFile:
    filename: str
    file: BytesIO


def parse_multipart_files(
    stream: BinaryIO,
    content_type: str,
    content_length: int,
    *,
    field_name: str = "files",
    max_bytes: int = MAX_UPLOAD_REQUEST_BYTES,
) -> list[UploadedFile]:
    """Decode file fields from one bounded multipart/form-data request."""
    if not content_type.lower().startswith("multipart/form-data"):
        raise ValueError("Expected multipart file upload")
    if "boundary=" not in content_type.lower():
        raise ValueError("Multipart boundary is missing")
    if content_length <= 0:
        raise ValueError("Upload request is empty")
    if content_length > max_bytes:
        raise ValueError(f"Upload request exceeds the {max_bytes // (1024 * 1024)} MB limit")
    body = stream.read(content_length)
    if len(body) != content_length:
        raise ValueError("Upload request ended before all bytes were received")
    message = BytesParser(policy=policy.default).parsebytes(
        b"Content-Type: " + content_type.encode("utf-8") + b"\r\n"
        b"MIME-Version: 1.0\r\n\r\n" + body
    )
    if not message.is_multipart():
        raise ValueError("Multipart upload could not be decoded")
    uploads: list[UploadedFile] = []
    for part in message.iter_parts():
        if part.get_content_disposition() != "form-data":
            continue
        if part.get_param("name", header="content-disposition") != field_name:
            continue
        filename = part.get_filename()
        if filename is None:
            continue
        payload = part.get_payload(decode=True)
        if payload is None:
            payload = b""
        uploads.append(UploadedFile(filename=filename, file=BytesIO(payload)))
    return uploads
