from __future__ import annotations

import unittest
from contextlib import redirect_stderr
from io import StringIO
from unittest.mock import patch

from clearspend.server import main


class ServerStartupSelectionTests(unittest.TestCase):
    def test_backend_selection_is_required(self) -> None:
        with patch("sys.argv", ["clearspend-server"]):
            with redirect_stderr(StringIO()):
                with self.assertRaises(SystemExit) as raised:
                    main()

        self.assertEqual(raised.exception.code, 2)

    def test_sqlite_migration_requires_explicit_legacy_database(self) -> None:
        with patch("sys.argv", ["clearspend-server", "--migrate-database"]):
            with redirect_stderr(StringIO()):
                with self.assertRaises(SystemExit) as raised:
                    main()

        self.assertEqual(raised.exception.code, 2)

    def test_old_implicit_sqlite_option_is_rejected(self) -> None:
        with patch("sys.argv", ["clearspend-server", "--database", "synthetic.db"]):
            with redirect_stderr(StringIO()):
                with self.assertRaises(SystemExit) as raised:
                    main()

        self.assertEqual(raised.exception.code, 2)


if __name__ == "__main__":
    unittest.main()
