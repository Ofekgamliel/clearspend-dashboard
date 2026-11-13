"""Application workflows for transaction-specific corrections."""

from __future__ import annotations

from datetime import date, datetime
from pathlib import Path

from clearspend.database.connection import connect_database
from clearspend.reporting.personal_spending import (
    personal_spending_amount,
    review_reimbursement,
)


def save_transaction_category(
    database: Path, transaction_id: int, category: str, subcategory: str,
) -> dict:
    category = category.strip()
    subcategory = subcategory.strip()
    if transaction_id <= 0 or not category:
        raise ValueError("Transaction and category are required")
    connection = connect_database(database)
    try:
        row = connection.execute(
            "SELECT merchant_raw FROM transactions WHERE id=?", (transaction_id,)
        ).fetchone()
        if not row:
            raise ValueError("Transaction was not found")
        now = datetime.now().astimezone().isoformat()
        connection.execute(
            """INSERT INTO transaction_category_overrides(transaction_id,category,subcategory,updated_at)
            VALUES(?,?,?,?) ON CONFLICT(transaction_id) DO UPDATE SET
            category=excluded.category,subcategory=excluded.subcategory,updated_at=excluded.updated_at""",
            (transaction_id, category, subcategory or None, now),
        )
        connection.commit()
        return {
            "status": "saved",
            "transaction_id": transaction_id,
            "merchant_raw": row[0],
            "category": category,
            "subcategory": subcategory or None,
        }
    finally:
        connection.close()


def save_transaction_adjustment(
    database: Path,
    transaction_id: int,
    reimbursed_amount: float,
    reimbursement_date: str,
    note: str,
    remove: bool = False,
) -> dict:
    if transaction_id <= 0:
        raise ValueError("Transaction is required")
    connection = connect_database(database)
    try:
        row = connection.execute(
            "SELECT merchant_raw,CAST(charged_amount AS REAL) amount FROM transactions WHERE id=?",
            (transaction_id,),
        ).fetchone()
        if not row:
            raise ValueError("Transaction was not found")
        charge = float(row["amount"] or 0)
        if charge <= 0:
            raise ValueError("Only positive card charges can be marked as reimbursed")
        if remove:
            connection.execute(
                "DELETE FROM transaction_spending_adjustments WHERE transaction_id=?",
                (transaction_id,),
            )
            connection.commit()
            return {
                "status": "removed", "transaction_id": transaction_id,
                "merchant_raw": row["merchant_raw"],
                "personal_amount": round(personal_spending_amount(charge), 2),
            }
        reviewed = review_reimbursement(charge, reimbursed_amount)
        reimbursed_amount = reviewed.reimbursed_amount
        reimbursement_date = reimbursement_date.strip()
        if reimbursement_date:
            try:
                date.fromisoformat(reimbursement_date)
            except ValueError as error:
                raise ValueError("Reimbursement date must be a valid date") from error
        note = note.strip()
        if len(note) > 500:
            raise ValueError("Note must be 500 characters or fewer")
        adjustment_type = reviewed.adjustment_type
        now = datetime.now().astimezone().isoformat()
        connection.execute(
            """INSERT INTO transaction_spending_adjustments(
            transaction_id,adjustment_type,reimbursed_amount,reimbursement_date,note,updated_at
            ) VALUES(?,?,?,?,?,?) ON CONFLICT(transaction_id) DO UPDATE SET
            adjustment_type=excluded.adjustment_type,
            reimbursed_amount=excluded.reimbursed_amount,
            reimbursement_date=excluded.reimbursement_date,
            note=excluded.note,updated_at=excluded.updated_at""",
            (
                transaction_id, adjustment_type, f"{reimbursed_amount:.2f}",
                reimbursement_date or None, note or None, now,
            ),
        )
        connection.commit()
        return {
            "status": "saved", "transaction_id": transaction_id,
            "merchant_raw": row["merchant_raw"], "adjustment_type": adjustment_type,
            "reimbursed_amount": reimbursed_amount,
            "personal_amount": reviewed.personal_amount,
        }
    finally:
        connection.close()
