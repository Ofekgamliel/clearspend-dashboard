from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any


def connect_database(
    path: Path | str,
    *,
    row_factory: Any = sqlite3.Row,
    enforce_foreign_keys: bool = False,
) -> sqlite3.Connection:
    """Open an application database connection with explicit shared defaults.

    Foreign-key enforcement remains opt-in to preserve the established runtime
    behavior during this structural refactor. Migration connections enable it
    independently.
    """
    connection = sqlite3.connect(path)
    connection.row_factory = row_factory
    if enforce_foreign_keys:
        connection.execute("PRAGMA foreign_keys = ON")
    return connection
