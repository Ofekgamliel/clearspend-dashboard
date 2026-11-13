from __future__ import annotations


def staged_transaction_summary(item, filename: str, file_index: int) -> dict:
    """Convert a canonical transaction into the staged-review response shape."""
    return {
        "filename": filename,
        "file_index": file_index,
        "transaction_key": item.transaction_key,
        "merchant": item.merchant_raw,
        "merchant_normalized": item.merchant_normalized,
        "transaction_date": item.transaction_date,
        "billing_date": item.billing_date,
        "billing_month": item.billing_month,
        "amount": item.charged_amount,
        "currency": item.charged_currency,
        "original_amount": item.original_amount,
        "original_currency": item.original_currency,
        "provider": item.provider,
        "card_last4": item.card_last4,
        "voucher_number": item.voucher_number,
        "installment_number": item.installment_number,
        "installment_total": item.installment_total,
        "notes": item.notes,
        "source_status": "pending" if item.charged_amount is None else
            "outside_cycle" if item.source_sheet.endswith(":immediate") else "monthly",
    }


def statement_reconciliation_total(statement) -> float:
    """Total only rows belonging to the statement's scheduled monthly charge."""
    return round(sum(
        float(item.charged_amount or 0)
        for item in statement.transactions
        if not item.source_sheet.endswith(":immediate")
    ), 2)
