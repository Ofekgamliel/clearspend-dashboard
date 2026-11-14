from __future__ import annotations

import json
from typing import BinaryIO


DEFAULT_JSON_LIMIT = 1024 * 1024


def read_json_object(
    stream: BinaryIO,
    content_length: str | int | None,
    *,
    max_bytes: int = DEFAULT_JSON_LIMIT,
) -> dict:
    """Read one bounded JSON request body and require an object at its root."""
    try:
        length = int(content_length or 0)
    except (TypeError, ValueError) as error:
        raise ValueError("Content-Length must be an integer") from error
    if length < 0:
        raise ValueError("Content-Length cannot be negative")
    if length > max_bytes:
        raise ValueError(f"JSON request exceeds the {max_bytes // (1024 * 1024)} MB limit")
    if length == 0:
        return {}
    body = stream.read(length)
    if len(body) != length:
        raise ValueError("JSON request ended before all bytes were received")
    payload = json.loads(body)
    if not isinstance(payload, dict):
        raise ValueError("JSON request body must be an object")
    return payload
