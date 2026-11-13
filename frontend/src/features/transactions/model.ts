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

export type MerchantGroupSortKey = 'merchant' | 'transactions' | 'latest_date' | 'amount';
export interface MerchantGroupSort { key: MerchantGroupSortKey; direction: 'asc' | 'desc' }
export interface TransactionMerchantGroup {
  key: string;
  display_name: string;
  aliases: string[];
  transactions: TransactionRow[];
  count: number;
  latest_date: string;
  amount: number;
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

export function groupTransactionsByMerchant(rows: TransactionRow[]): TransactionMerchantGroup[] {
  const groups = new Map<string, TransactionMerchantGroup>();
  for (const row of rows) {
    const key = row.canonical_merchant_id || row.merchant_normalized;
    let group = groups.get(key);
    if (!group) {
      group = { key, display_name: row.merchant_display_name || row.merchant_raw, aliases: [], transactions: [], count: 0, latest_date: '', amount: 0 };
      groups.set(key, group);
    }
    if (!group.aliases.includes(row.merchant_raw)) group.aliases.push(row.merchant_raw);
    group.transactions.push(row);
    group.count += 1;
    group.amount += Number(row.personal_amount ?? row.amount ?? 0);
    if ((row.transaction_date ?? '') > group.latest_date) group.latest_date = row.transaction_date ?? '';
  }
  return [...groups.values()].map((group) => ({
    ...group,
    amount: Math.round(group.amount * 100) / 100,
    transactions: sortTransactions(group.transactions, { key: 'transaction_date', direction: 'desc' }),
  }));
}

export function sortMerchantGroups(groups: TransactionMerchantGroup[], sort: MerchantGroupSort): TransactionMerchantGroup[] {
  return [...groups].sort((left, right) => {
    let comparison = 0;
    if (sort.key === 'merchant') comparison = collator.compare(left.display_name, right.display_name);
    else if (sort.key === 'transactions') comparison = left.count - right.count;
    else if (sort.key === 'amount') comparison = left.amount - right.amount;
    else comparison = left.latest_date.localeCompare(right.latest_date);
    return sort.direction === 'asc' ? comparison : -comparison;
  });
}

export function nextMerchantGroupSort(current: MerchantGroupSort, key: MerchantGroupSortKey): MerchantGroupSort {
  return current.key === key
    ? { key, direction: current.direction === 'asc' ? 'desc' : 'asc' }
    : { key, direction: key === 'merchant' ? 'asc' : 'desc' };
}
