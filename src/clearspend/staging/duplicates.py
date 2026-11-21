from __future__ import annotations

from typing import Any


def possible_duplicate_matches(
    connection: Any, item
) -> tuple[list[Any], str | None]:
    """Find conservative non-exact matches. A different voucher proves two rows are distinct."""
    if item.voucher_number:
        rows = connection.execute(
            """SELECT id,transaction_key,merchant_raw,transaction_date,billing_date,billing_month,
            charged_amount,charged_currency,voucher_number FROM transactions
            WHERE provider=? AND card_last4=? AND voucher_number=? AND transaction_key<>?
            ORDER BY id""",
            (item.provider, item.card_last4, item.voucher_number, item.transaction_key),
        ).fetchall()
        reason = "Same card and provider reference, but other statement details changed"
        return rows, reason if rows else None
    rows = connection.execute(
        """SELECT id,transaction_key,merchant_raw,transaction_date,billing_date,billing_month,
        charged_amount,charged_currency,voucher_number,installment_number FROM transactions
        WHERE provider=? AND card_last4=?
        AND transaction_date IS NOT DISTINCT FROM ? AND merchant_normalized=?
        AND charged_amount IS NOT DISTINCT FROM ?
        AND charged_currency IS NOT DISTINCT FROM ?
        AND original_amount IS NOT DISTINCT FROM ?
        AND original_currency IS NOT DISTINCT FROM ?
        AND transaction_key<>? ORDER BY id""",
        (item.provider, item.card_last4, item.transaction_date, item.merchant_normalized,
         item.charged_amount, item.charged_currency, item.original_amount,
         item.original_currency, item.transaction_key),
    ).fetchall()
    rows = [row for row in rows if not (
        item.installment_number is not None and row["installment_number"] is not None
        and int(item.installment_number) != int(row["installment_number"])
    )]
    reason = "Same card, purchase date, merchant and amount; billing details differ"
    return rows, reason if rows else None
