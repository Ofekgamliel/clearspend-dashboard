from __future__ import annotations

import hashlib
import json
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import Any

from clearspend.database.connection import connect_database
from clearspend.database.migration_runner import MigrationError, inspect_database, migrate_database
from clearspend.database.settings import DatabaseBackend
from clearspend.imports.dispatch import parse_statement
from clearspend.imports.income import is_income_xlsx, parse_income_xlsx
from clearspend.imports.metadata_policy import (
    ImportMetadataPolicy,
    metadata_policy_for_backend,
)
from tools.profile_samples import sha256_path


class ImportDatabase:
    """Persistence boundary for statement and income imports."""

    def __init__(
        self,
        path: Path,
        *,
        metadata_policy: ImportMetadataPolicy | None = None,
    ):
        status = inspect_database(path)
        if status.state == "empty":
            migrate_database(path)
        elif status.state == "unsupported":
            raise MigrationError("Unsupported database schema: " + "; ".join(status.problems))
        self.connection = connect_database(path)
        self._owns_connection = True
        self.metadata_policy = metadata_policy or metadata_policy_for_backend(
            DatabaseBackend.SQLITE
        )

    @classmethod
    def from_connection(
        cls,
        connection: Any,
        backend: DatabaseBackend,
        *,
        metadata_policy: ImportMetadataPolicy | None = None,
    ) -> ImportDatabase:
        """Bind import persistence to a caller-owned transaction connection."""
        database = cls.__new__(cls)
        database.connection = connection
        database._owns_connection = False
        database.metadata_policy = metadata_policy or metadata_policy_for_backend(backend)
        return database

    def close(self) -> None:
        if self._owns_connection:
            self.connection.close()

    def _insert_id(self, sql: str, parameters: tuple[Any, ...]) -> int:
        row = self.connection.execute(sql + " RETURNING id", parameters).fetchone()
        if row is None:
            raise RuntimeError("Import persistence did not return an identity")
        return int(row["id"])

    def _commit(self, commit: bool) -> None:
        if commit:
            self.connection.commit()

    def _relevant_transactions(
        self,
        transactions: list[Any],
        reviewed_ids: set[int],
    ) -> list[Any]:
        """Load every existing row needed for import identity decisions at once."""
        base_keys = sorted({item.base_key for item in transactions})
        transaction_keys = sorted({item.transaction_key for item in transactions})
        conditions: list[str] = []
        parameters: list[Any] = []
        for column, values in (
            ("base_key", base_keys),
            ("transaction_key", transaction_keys),
            ("id", sorted(reviewed_ids)),
        ):
            if values:
                conditions.append(f"{column} IN ({','.join('?' for _ in values)})")
                parameters.extend(values)
        if not conditions:
            return []
        return self.connection.execute(
            """SELECT id,transaction_key,base_key,occurrence,provider,card_last4,
            voucher_number FROM transactions WHERE """ + " OR ".join(conditions)
            + " ORDER BY id",
            parameters,
        ).fetchall()

    def _insert_transaction_batch(
        self,
        rows: list[tuple[list[str], list[Any]]],
    ) -> dict[str, int]:
        """Insert bounded multi-row batches and return identities keyed by transaction key."""
        inserted: dict[str, int] = {}
        batch_size = 25
        for offset in range(0, len(rows), batch_size):
            batch = rows[offset:offset + batch_size]
            columns = batch[0][0]
            row_placeholders = f"({','.join('?' for _ in columns)})"
            result = self.connection.execute(
                f"""INSERT INTO transactions({','.join(columns)}) VALUES
                {','.join(row_placeholders for _ in batch)}
                ON CONFLICT(transaction_key) DO NOTHING RETURNING id,transaction_key""",
                [value for _, values in batch for value in values],
            ).fetchall()
            inserted.update({str(row["transaction_key"]): int(row["id"]) for row in result})
        return inserted

    def _insert_import_transaction_batch(
        self,
        import_id: int,
        links: list[tuple[int, int]],
    ) -> None:
        """Persist import audit links without one network round trip per row."""
        batch_size = 200
        for offset in range(0, len(links), batch_size):
            batch = links[offset:offset + batch_size]
            self.connection.execute(
                """INSERT INTO import_transactions(import_id,transaction_id,was_duplicate)
                VALUES """ + ",".join("(?,?,?)" for _ in batch)
                + " ON CONFLICT(import_id,transaction_id) DO NOTHING",
                [value for transaction_id, was_duplicate in batch
                 for value in (import_id, transaction_id, was_duplicate)],
            )

    def import_statement(self, path: Path, probable_duplicate_matches: dict[str, int] | None = None,
                         excluded_transaction_keys: set[str] | None = None, *,
                         original_name: str | None = None,
                         commit: bool = True) -> dict[str, Any]:
        probable_duplicate_matches = probable_duplicate_matches or {}
        excluded_transaction_keys = excluded_transaction_keys or set()
        byte_hash = sha256_path(path)
        source_format = path.suffix.lower()
        stored_name = original_name or path.name
        stored_path = self.metadata_policy.source_path(path, stored_name)
        prior_file = self.connection.execute(
            "SELECT * FROM imports WHERE byte_hash = ? AND status IN ('imported', 'duplicate_file') ORDER BY id LIMIT 1",
            (byte_hash,),
        ).fetchone()
        now = datetime.now().astimezone().isoformat()
        if prior_file:
            import_id = self._insert_id(
                """INSERT INTO imports(original_name,source_path,byte_hash,source_format,status,imported_at,
                provider,card_last4,parsed_rows,inserted_rows,duplicate_rows)
                VALUES(?,?,?,?,?,?,?,?,?,?,?)""",
                (stored_name, stored_path, byte_hash, source_format, "duplicate_file", now,
                 prior_file["provider"], prior_file["card_last4"], prior_file["parsed_rows"], 0, prior_file["parsed_rows"]),
            )
            self._commit(commit)
            return {"import_id": import_id, "status": "duplicate_file", "matches_import_id": prior_file["id"]}

        try:
            statement = parse_statement(path)
        except Exception as error:
            import_id = self._insert_id(
                """INSERT INTO imports(original_name,source_path,byte_hash,source_format,status,imported_at,error_message)
                VALUES(?,?,?,?,?,?,?)""",
                (
                    stored_name,
                    stored_path,
                    byte_hash,
                    source_format,
                    "failed",
                    now,
                    self.metadata_policy.error_message(str(error)),
                ),
            )
            self._commit(commit)
            return {"import_id": import_id, "status": "failed", "error": str(error)}

        semantic_hash = statement.semantic_hash
        prior_semantic = self.connection.execute(
            "SELECT id FROM imports WHERE semantic_hash = ? AND status IN ('imported', 'duplicate_content') ORDER BY id LIMIT 1",
            (semantic_hash,),
        ).fetchone()
        status = "duplicate_content" if prior_semantic else "imported"
        import_id = self._insert_id(
            """INSERT INTO imports(original_name,source_path,byte_hash,semantic_hash,source_format,provider,card_last4,
            product_name,statement_range,status,parsed_rows,imported_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)""",
            (stored_name, stored_path, byte_hash, semantic_hash, source_format, statement.provider, statement.card_last4,
             statement.product_name, statement.date_range, status, len(statement.transactions), now),
        )
        active_transactions = [
            transaction for transaction in statement.transactions
            if transaction.transaction_key not in excluded_transaction_keys
        ]
        reviewed_ids = {
            int(match_id) for transaction in active_transactions
            if (match_id := probable_duplicate_matches.get(transaction.transaction_key)) is not None
        }
        relevant_rows = self._relevant_transactions(active_transactions, reviewed_ids)
        existing_by_id = {int(row["id"]): row for row in relevant_rows}
        missing_reviewed_ids = reviewed_ids - set(existing_by_id)
        if missing_reviewed_ids:
            missing_id = min(missing_reviewed_ids)
            raise ValueError(f"Reviewed duplicate transaction {missing_id} no longer exists")

        known_by_key: dict[str, dict[str, Any]] = {
            str(row["transaction_key"]): {
                "id": int(row["id"]),
                "transaction_key": str(row["transaction_key"]),
                "voucher_number": row["voucher_number"],
            }
            for row in relevant_rows
        }
        known_by_voucher: dict[tuple[str, str, str, str], dict[str, Any]] = {}
        max_occurrence: dict[str, int] = {}
        for row in relevant_rows:
            base_key = str(row["base_key"])
            max_occurrence[base_key] = max(
                max_occurrence.get(base_key, 0), int(row["occurrence"])
            )
            if row["voucher_number"]:
                known_by_voucher.setdefault(
                    (
                        str(row["provider"]), str(row["card_last4"]),
                        str(row["voucher_number"]), base_key,
                    ),
                    known_by_key[str(row["transaction_key"])],
                )

        planned_rows: list[tuple[list[str], list[Any]]] = []
        decisions: list[tuple[str, bool]] = []
        reviewed_duplicates = 0
        for transaction in active_transactions:
            voucher_exact = None
            if transaction.voucher_number:
                voucher_exact = known_by_voucher.get(
                    (
                        transaction.provider, transaction.card_last4,
                        transaction.voucher_number, transaction.base_key,
                    )
                )
            if voucher_exact is not None:
                decisions.append((str(voucher_exact["transaction_key"]), True))
                continue
            reviewed_match_id = probable_duplicate_matches.get(transaction.transaction_key)
            if reviewed_match_id is not None:
                decisions.append((str(existing_by_id[int(reviewed_match_id)]["transaction_key"]), True))
                reviewed_duplicates += 1
                continue
            key_collision = known_by_key.get(transaction.transaction_key)
            if (key_collision and transaction.voucher_number and key_collision["voucher_number"]
                    and transaction.voucher_number != key_collision["voucher_number"]):
                transaction.occurrence = max_occurrence.get(transaction.base_key, 0) + 1
                transaction.transaction_key = hashlib.sha256(
                    f"{transaction.base_key}:{transaction.occurrence}".encode()
                ).hexdigest()
            existing = known_by_key.get(transaction.transaction_key)
            if existing is not None:
                decisions.append((str(existing["transaction_key"]), True))
                continue
            fields = asdict(transaction)
            source_payload = self.metadata_policy.source_payload(fields.pop("source_payload"))
            payload = (
                json.dumps(source_payload, ensure_ascii=False, sort_keys=True)
                if source_payload is not None
                else None
            )
            columns = list(fields) + ["source_payload", "first_import_id", "created_at"]
            values = list(fields.values()) + [payload, import_id, now]
            planned_rows.append((columns, values))
            reference = {
                "id": None,
                "transaction_key": transaction.transaction_key,
                "voucher_number": transaction.voucher_number,
            }
            known_by_key[transaction.transaction_key] = reference
            if transaction.voucher_number:
                known_by_voucher.setdefault(
                    (
                        transaction.provider, transaction.card_last4,
                        transaction.voucher_number, transaction.base_key,
                    ),
                    reference,
                )
            max_occurrence[transaction.base_key] = max(
                max_occurrence.get(transaction.base_key, 0), transaction.occurrence
            )
            decisions.append((transaction.transaction_key, False))

        inserted_by_key = self._insert_transaction_batch(planned_rows) if planned_rows else {}
        planned_keys = [str(values[columns.index("transaction_key")]) for columns, values in planned_rows]
        conflicted_keys = sorted(set(planned_keys) - set(inserted_by_key))
        if conflicted_keys:
            conflict_rows = self.connection.execute(
                "SELECT id,transaction_key FROM transactions WHERE transaction_key IN ("
                + ",".join("?" for _ in conflicted_keys) + ")",
                conflicted_keys,
            ).fetchall()
            inserted_by_key.update({
                str(row["transaction_key"]): int(row["id"]) for row in conflict_rows
            })
        unresolved = set(planned_keys) - set(inserted_by_key)
        if unresolved:
            raise RuntimeError("Imported transaction identities could not be resolved")
        for transaction_key, transaction_id in inserted_by_key.items():
            known_by_key[transaction_key]["id"] = transaction_id

        inserted_keys = {
            str(row["transaction_key"])
            for row in self.connection.execute(
                "SELECT transaction_key FROM transactions WHERE first_import_id=?",
                (import_id,),
            ).fetchall()
        } if planned_rows else set()
        links = [
            (int(known_by_key[transaction_key]["id"]), int(was_duplicate or transaction_key not in inserted_keys))
            for transaction_key, was_duplicate in decisions
        ]
        self._insert_import_transaction_batch(import_id, links)
        inserted = sum(1 for transaction_key, duplicate in decisions
                       if not duplicate and transaction_key in inserted_keys)
        duplicates = sum(1 for transaction_key, duplicate in decisions
                         if duplicate or transaction_key not in inserted_keys)
        self.connection.execute(
            "UPDATE imports SET inserted_rows=?, duplicate_rows=? WHERE id=?", (inserted, duplicates, import_id)
        )
        self._commit(commit)
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

    def import_income(
        self,
        path: Path,
        *,
        original_name: str | None = None,
        commit: bool = True,
    ) -> dict[str, Any]:
        if path.suffix.lower() != ".xlsx":
            raise ValueError("Income files must use XLSX format")
        byte_hash = sha256_path(path)
        now = datetime.now().astimezone().isoformat()
        stored_name = original_name or path.name
        stored_path = self.metadata_policy.source_path(path, stored_name)
        prior_file = self.connection.execute(
            "SELECT id,parsed_rows FROM income_imports WHERE byte_hash=? AND status IN ('imported','duplicate_file') ORDER BY id LIMIT 1",
            (byte_hash,),
        ).fetchone()
        if prior_file:
            import_id = self._insert_id(
                """INSERT INTO income_imports(original_name,source_path,byte_hash,source_format,status,
                parsed_rows,inserted_rows,duplicate_rows,imported_at) VALUES(?,?,?,?,?,?,?,?,?)""",
                (stored_name, stored_path, byte_hash, ".xlsx", "duplicate_file", prior_file["parsed_rows"], 0,
                 prior_file["parsed_rows"], now),
            )
            self._commit(commit)
            return {"import_id": import_id, "status": "duplicate_file", "kind": "income",
                    "matches_import_id": prior_file["id"]}
        try:
            entries = parse_income_xlsx(path)
        except Exception as error:
            import_id = self._insert_id(
                """INSERT INTO income_imports(original_name,source_path,byte_hash,source_format,status,
                imported_at,error_message) VALUES(?,?,?,?,?,?,?)""",
                (
                    stored_name,
                    stored_path,
                    byte_hash,
                    ".xlsx",
                    "failed",
                    now,
                    self.metadata_policy.error_message(str(error)),
                ),
            )
            self._commit(commit)
            return {"import_id": import_id, "status": "failed", "kind": "income", "error": str(error)}
        import_id = self._insert_id(
            """INSERT INTO income_imports(original_name,source_path,byte_hash,source_format,status,
            parsed_rows,imported_at) VALUES(?,?,?,?,?,?,?)""",
            (stored_name, stored_path, byte_hash, ".xlsx", "imported", len(entries), now),
        )
        inserted = duplicates = 0
        for entry in entries:
            row = self.connection.execute(
                    """INSERT INTO income_entries(month,source_name,amount,entry_key,first_import_id,created_at)
                    VALUES(?,?,?,?,?,?) ON CONFLICT(entry_key) DO NOTHING RETURNING id""",
                    (entry.month, entry.source_name, entry.amount, entry.entry_key, import_id, now),
                ).fetchone()
            if row is not None:
                inserted += 1
            else:
                duplicates += 1
        status = "duplicate_content" if inserted == 0 else "imported"
        self.connection.execute(
            "UPDATE income_imports SET status=?,inserted_rows=?,duplicate_rows=? WHERE id=?",
            (status, inserted, duplicates, import_id),
        )
        self._commit(commit)
        return {"import_id": import_id, "status": status, "kind": "income", "parsed": len(entries),
                "inserted": inserted, "duplicates": duplicates}

    def import_file(self, path: Path, probable_duplicate_matches: dict[str, int] | None = None,
                    excluded_transaction_keys: set[str] | None = None, *,
                    original_name: str | None = None,
                    commit: bool = True) -> dict[str, Any]:
        return self.import_income(
            path,
            original_name=original_name,
            commit=commit,
        ) if is_income_xlsx(path) else self.import_statement(
            path, probable_duplicate_matches=probable_duplicate_matches,
            excluded_transaction_keys=excluded_transaction_keys,
            original_name=original_name,
            commit=commit,
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
