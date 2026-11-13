import type { RecentTransaction, TransactionRow } from '../../api/contracts.ts';

export type TransactionSortKey =
  | 'merchant'
  | 'category'
  | 'card'
  | 'transaction_date'
  | 'billing_date'
  | 'billing_month'
  | 'amount'
  | 'original_amount'
  | 'transaction_type'
  | 'execution_method'
  | 'voucher_number'
  | 'exchange_rate'
  | 'notes';

export interface TransactionSort {
  key: TransactionSortKey;
  direction: 'asc' | 'desc';
}

export const transactionColumns: ReadonlyArray<readonly [TransactionSortKey, string]> = [
  ['merchant', 'Merchant'],
  ['category', 'Category / subcategory'],
  ['card', 'Provider / card / source'],
  ['transaction_date', 'Transaction date'],
  ['billing_date', 'Billing date'],
  ['billing_month', 'Reporting month'],
  ['amount', 'Charged amount'],
  ['original_amount', 'Original amount'],
  ['transaction_type', 'Transaction type'],
  ['execution_method', 'Execution method'],
  ['voucher_number', 'Voucher'],
  ['exchange_rate', 'Exchange rate'],
  ['notes', 'Notes'],
];

const numericKeys = new Set<TransactionSortKey>(['amount', 'original_amount', 'exchange_rate']);
const collator = new Intl.Collator(['he', 'en'], { numeric: true, sensitivity: 'base' });

function text(value: unknown): string {
  return String(value ?? '').trim();
}

export function transactionSortValue(row: TransactionRow, key: TransactionSortKey): unknown {
  if (key === 'merchant') return `${text(row.merchant_display_name)} ${text(row.merchant_raw)} ${text(row.merchant_normalized)}`;
  if (key === 'category') return `${text(row.category)} ${text(row.subcategory)}`;
  if (key === 'card') return `${text(row.provider)} ${text(row.card_last4)} ${text(row.source_sheet)}`;
  return row[key];
}

export function sortTransactions(rows: TransactionRow[], sort: TransactionSort): TransactionRow[] {
  return [...rows].sort((left, right) => {
    const leftValue = transactionSortValue(left, sort.key);
    const rightValue = transactionSortValue(right, sort.key);
    const leftEmpty = leftValue === null || leftValue === undefined || leftValue === '';
    const rightEmpty = rightValue === null || rightValue === undefined || rightValue === '';
    if (leftEmpty || rightEmpty) {
      if (leftEmpty && rightEmpty) return 0;
      return leftEmpty ? 1 : -1;
    }
    const comparison = numericKeys.has(sort.key)
      ? Number(leftValue) - Number(rightValue)
      : collator.compare(String(leftValue), String(rightValue));
    return sort.direction === 'asc' ? comparison : -comparison;
  });
}

export function reportingValue(row: RecentTransaction): string {
  return row.billing_date ?? (row.billing_month ? `${row.billing_month}-01` : row.transaction_date ?? '');
}

export function reportingSourceLabel(source: string | null): string {
  return ({
    provider: 'Provider billing date',
    statement: 'Statement month',
    estimated: 'Estimated installment month',
    purchase_date: 'Purchase date fallback',
  } as Record<string, string>)[source ?? ''] ?? 'Reporting month';
}

export function nextSort(current: TransactionSort, key: TransactionSortKey): TransactionSort {
  if (current.key !== key) return { key, direction: 'asc' };
  return { key, direction: current.direction === 'asc' ? 'desc' : 'asc' };
}
