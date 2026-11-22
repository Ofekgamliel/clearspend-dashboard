from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any


def connect_sqlite(
    path: Path,
    *,
    row_factory: Any = sqlite3.Row,
    enforce_foreign_keys: bool = False,
) -> sqlite3.Connection:
    """Open SQLite with the established ClearSpend runtime defaults."""
    connection = sqlite3.connect(path)
    connection.row_factory = row_factory
    if enforce_foreign_keys:
        connection.execute("PRAGMA foreign_keys = ON")
    return connection
