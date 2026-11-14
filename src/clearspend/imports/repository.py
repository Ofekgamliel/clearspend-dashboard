from __future__ import annotations

import hashlib
import json
import sqlite3
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import Any

from clearspend.database.connection import connect_database
from clearspend.database.migration_runner import MigrationError, inspect_database, migrate_database
from clearspend.imports.dispatch import parse_statement
from clearspend.imports.income import is_income_xlsx, parse_income_xlsx
from tools.profile_samples import sha256_path


class ImportDatabase:
    """Persistence boundary for statement and income imports."""

    def __init__(self, path: Path):
        status = inspect_database(path)
        if status.state == "empty":
            migrate_database(path)
        elif status.state == "unsupported":
            raise MigrationError("Unsupported database schema: " + "; ".join(status.problems))
        self.connection = connect_database(path)

    def close(self) -> None:
        self.connection.close()

    def import_statement(self, path: Path, probable_duplicate_matches: dict[str, int] | None = None,
                         excluded_transaction_keys: set[str] | None = None) -> dict[str, Any]:
        probable_duplicate_matches = probable_duplicate_matches or {}
        excluded_transaction_keys = excluded_transaction_keys or set()
        byte_hash = sha256_path(path)
        source_format = path.suffix.lower()
        prior_file = self.connection.execute(
            "SELECT * FROM imports WHERE byte_hash = ? AND status IN ('imported', 'duplicate_file') ORDER BY id LIMIT 1",
            (byte_hash,),
        ).fetchone()
        now = datetime.now().astimezone().isoformat()
        if prior_file:
            cursor = self.connection.execute(
                """INSERT INTO imports(original_name,source_path,byte_hash,source_format,status,imported_at,
                provider,card_last4,parsed_rows,inserted_rows,duplicate_rows)
                VALUES(?,?,?,?,?,?,?,?,?,?,?)""",
                (path.name, str(path), byte_hash, source_format, "duplicate_file", now,
                 prior_file["provider"], prior_file["card_last4"], prior_file["parsed_rows"], 0, prior_file["parsed_rows"]),
            )
            self.connection.commit()
            return {"import_id": cursor.lastrowid, "status": "duplicate_file", "matches_import_id": prior_file["id"]}

        try:
            statement = parse_statement(path)
        except Exception as error:
            cursor = self.connection.execute(
                """INSERT INTO imports(original_name,source_path,byte_hash,source_format,status,imported_at,error_message)
                VALUES(?,?,?,?,?,?,?)""",
                (path.name, str(path), byte_hash, source_format, "failed", now, str(error)),
            )
            self.connection.commit()
            return {"import_id": cursor.lastrowid, "status": "failed", "error": str(error)}

        semantic_hash = statement.semantic_hash
        prior_semantic = self.connection.execute(
            "SELECT id FROM imports WHERE semantic_hash = ? AND status IN ('imported', 'duplicate_content') ORDER BY id LIMIT 1",
            (semantic_hash,),
        ).fetchone()
        status = "duplicate_content" if prior_semantic else "imported"
        cursor = self.connection.execute(
            """INSERT INTO imports(original_name,source_path,byte_hash,semantic_hash,source_format,provider,card_last4,
            product_name,statement_range,status,parsed_rows,imported_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)""",
            (path.name, str(path), byte_hash, semantic_hash, source_format, statement.provider, statement.card_last4,
             statement.product_name, statement.date_range, status, len(statement.transactions), now),
        )
        import_id = cursor.lastrowid
        inserted = 0
        duplicates = 0
        reviewed_duplicates = 0
        for transaction in statement.transactions:
            if transaction.transaction_key in excluded_transaction_keys:
                continue
            voucher_exact_id = None
            if transaction.voucher_number:
                voucher_exact = self.connection.execute(
                    """SELECT id FROM transactions WHERE provider=? AND card_last4=?
                    AND voucher_number=? AND base_key=? ORDER BY id LIMIT 1""",
                    (transaction.provider, transaction.card_last4,
                     transaction.voucher_number, transaction.base_key),
                ).fetchone()
                voucher_exact_id = voucher_exact["id"] if voucher_exact else None
            if voucher_exact_id is not None:
                self.connection.execute(
                    "INSERT OR IGNORE INTO import_transactions(import_id,transaction_id,was_duplicate) VALUES(?,?,1)",
                    (import_id, voucher_exact_id),
                )
                duplicates += 1
                continue
            reviewed_match_id = probable_duplicate_matches.get(transaction.transaction_key)
            if reviewed_match_id is not None:
                matched = self.connection.execute(
                    "SELECT id FROM transactions WHERE id=?", (reviewed_match_id,)
                ).fetchone()
                if not matched:
                    raise ValueError(f"Reviewed duplicate transaction {reviewed_match_id} no longer exists")
                self.connection.execute(
                    "INSERT OR IGNORE INTO import_transactions(import_id,transaction_id,was_duplicate) VALUES(?,?,1)",
                    (import_id, reviewed_match_id),
                )
                duplicates += 1
                reviewed_duplicates += 1
                continue
            key_collision = self.connection.execute(
                "SELECT id,voucher_number FROM transactions WHERE transaction_key=?",
                (transaction.transaction_key,),
            ).fetchone()
            if (key_collision and transaction.voucher_number and key_collision["voucher_number"]
                    and transaction.voucher_number != key_collision["voucher_number"]):
                max_occurrence = self.connection.execute(
                    "SELECT COALESCE(MAX(occurrence),0) FROM transactions WHERE base_key=?",
                    (transaction.base_key,),
                ).fetchone()[0]
                transaction.occurrence = int(max_occurrence) + 1
                transaction.transaction_key = hashlib.sha256(
                    f"{transaction.base_key}:{transaction.occurrence}".encode()
                ).hexdigest()
            fields = asdict(transaction)
            payload = json.dumps(fields.pop("source_payload"), ensure_ascii=False, sort_keys=True)
            columns = list(fields) + ["source_payload", "first_import_id", "created_at"]
            values = list(fields.values()) + [payload, import_id, now]
            placeholders = ",".join("?" for _ in columns)
            try:
                transaction_cursor = self.connection.execute(
                    f"INSERT INTO transactions({','.join(columns)}) VALUES({placeholders})", values
                )
                transaction_id = transaction_cursor.lastrowid
                was_duplicate = 0
                inserted += 1
            except sqlite3.IntegrityError:
                transaction_id = self.connection.execute(
                    "SELECT id FROM transactions WHERE transaction_key = ?", (transaction.transaction_key,)
                ).fetchone()["id"]
                was_duplicate = 1
                duplicates += 1
            self.connection.execute(
                "INSERT OR IGNORE INTO import_transactions(import_id,transaction_id,was_duplicate) VALUES(?,?,?)",
                (import_id, transaction_id, was_duplicate),
            )
        self.connection.execute(
            "UPDATE imports SET inserted_rows=?, duplicate_rows=? WHERE id=?", (inserted, duplicates, import_id)
        )
        self.connection.commit()
        return {
            "import_id": import_id,
            "status": status,
            "provider": statement.provider,
            "card_last4": statement.card_last4,
            "parsed": len(statement.transactions),
            "inserted": inserted,
            "duplicates": duplicates,
            "reviewed_duplicates": reviewed_duplicates,
            "matches_import_id": prior_semantic["id"] if prior_semantic else None,
        }

    def import_income(self, path: Path) -> dict[str, Any]:
        if path.suffix.lower() != ".xlsx":
            raise ValueError("Income files must use XLSX format")
        byte_hash = sha256_path(path)
        now = datetime.now().astimezone().isoformat()
        prior_file = self.connection.execute(
            "SELECT id,parsed_rows FROM income_imports WHERE byte_hash=? AND status IN ('imported','duplicate_file') ORDER BY id LIMIT 1",
            (byte_hash,),
        ).fetchone()
        if prior_file:
            cursor = self.connection.execute(
                """INSERT INTO income_imports(original_name,source_path,byte_hash,source_format,status,
                parsed_rows,inserted_rows,duplicate_rows,imported_at) VALUES(?,?,?,?,?,?,?,?,?)""",
                (path.name, str(path), byte_hash, ".xlsx", "duplicate_file", prior_file["parsed_rows"], 0,
                 prior_file["parsed_rows"], now),
            )
            self.connection.commit()
            return {"import_id": cursor.lastrowid, "status": "duplicate_file", "kind": "income",
                    "matches_import_id": prior_file["id"]}
        try:
            entries = parse_income_xlsx(path)
        except Exception as error:
            cursor = self.connection.execute(
                """INSERT INTO income_imports(original_name,source_path,byte_hash,source_format,status,
                imported_at,error_message) VALUES(?,?,?,?,?,?,?)""",
                (path.name, str(path), byte_hash, ".xlsx", "failed", now, str(error)),
            )
            self.connection.commit()
            return {"import_id": cursor.lastrowid, "status": "failed", "kind": "income", "error": str(error)}
        cursor = self.connection.execute(
            """INSERT INTO income_imports(original_name,source_path,byte_hash,source_format,status,
            parsed_rows,imported_at) VALUES(?,?,?,?,?,?,?)""",
            (path.name, str(path), byte_hash, ".xlsx", "imported", len(entries), now),
        )
        import_id = cursor.lastrowid
        inserted = duplicates = 0
        for entry in entries:
            try:
                self.connection.execute(
                    """INSERT INTO income_entries(month,source_name,amount,entry_key,first_import_id,created_at)
                    VALUES(?,?,?,?,?,?)""",
                    (entry.month, entry.source_name, entry.amount, entry.entry_key, import_id, now),
                )
                inserted += 1
            except sqlite3.IntegrityError:
                duplicates += 1
        status = "duplicate_content" if inserted == 0 else "imported"
        self.connection.execute(
            "UPDATE income_imports SET status=?,inserted_rows=?,duplicate_rows=? WHERE id=?",
            (status, inserted, duplicates, import_id),
        )
        self.connection.commit()
        return {"import_id": import_id, "status": status, "kind": "income", "parsed": len(entries),
                "inserted": inserted, "duplicates": duplicates}

    def import_file(self, path: Path, probable_duplicate_matches: dict[str, int] | None = None,
                    excluded_transaction_keys: set[str] | None = None) -> dict[str, Any]:
        return self.import_income(path) if is_income_xlsx(path) else self.import_statement(
            path, probable_duplicate_matches=probable_duplicate_matches,
            excluded_transaction_keys=excluded_transaction_keys,
        )

    def summary(self) -> dict[str, Any]:
        imports = self.connection.execute(
            "SELECT status, COUNT(*) AS count FROM imports GROUP BY status ORDER BY status"
        ).fetchall()
        cards = self.connection.execute(
            """SELECT provider, card_last4, COUNT(*) AS transactions,
            MIN(transaction_date) AS first_date, MAX(transaction_date) AS last_date
            FROM transactions GROUP BY provider, card_last4 ORDER BY provider, card_last4"""
        ).fetchall()
        return {"imports": [dict(row) for row in imports], "cards": [dict(row) for row in cards]}
