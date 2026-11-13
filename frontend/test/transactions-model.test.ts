import assert from 'node:assert/strict';
import test from 'node:test';
import type { TransactionRow } from '../src/api/contracts.ts';
import { transactionsUrl } from '../src/api/transactions.ts';
import { nextSort, reportingSourceLabel, reportingValue, sortTransactions } from '../src/features/transactions/model.ts';

function row(overrides: Partial<TransactionRow>): TransactionRow {
  return {
    id: 1,
    merchant_raw: 'Synthetic merchant',
    merchant_normalized: 'synthetic merchant',
    canonical_merchant_id: 'synthetic merchant',
    merchant_display_name: 'Synthetic merchant',
    category: 'Food',
    subcategory: null,
    merchant_category: 'Food',
    category_source: 'merchant_rule',
    provider: 'provider',
    card_last4: '1234',
    source_sheet: 'Sheet 1',
    transaction_date: '2026-03-02',
    billing_date: '2026-03-10',
    billing_month: '2026-03',
    billing_month_source: 'provider',
    installment_number: null,
    installment_total: null,
    amount: 20,
    personal_amount: 20,
    charged_currency: 'ILS',
    adjustment_type: null,
    reimbursed_amount: null,
    reimbursement_date: null,
    reimbursement_note: null,
    original_amount: null,
    original_currency: null,
    transaction_type: null,
    voucher_number: null,
    notes: null,
    execution_method: null,
    exchange_rate: null,
    event_id: null,
    event_name: null,
    event_type: null,
    event_destination: null,
    ...overrides,
  };
}

test('builds a complete-history substring search URL within current filters', () => {
  const url = transactionsUrl({
    period: 'all', card: 'provider:1234', search: 'merchant name', category: 'Food & drink', eventScope: 'routine',
  });
  const parsed = new URL(url, 'http://localhost');
  assert.equal(parsed.pathname, '/api/transactions');
  assert.equal(parsed.searchParams.get('q'), 'merchant name');
  assert.equal(parsed.searchParams.get('category'), 'Food & drink');
  assert.equal(parsed.searchParams.get('card'), 'provider:1234');
  assert.equal(parsed.searchParams.get('event_scope'), 'routine');
});

test('sorts transaction dates descending without mutating the response', () => {
  const rows = [row({ id: 1, transaction_date: '2026-03-01' }), row({ id: 2, transaction_date: '2026-03-08' })];
  const sorted = sortTransactions(rows, { key: 'transaction_date', direction: 'desc' });
  assert.deepEqual(sorted.map((item) => item.id), [2, 1]);
  assert.deepEqual(rows.map((item) => item.id), [1, 2]);
});

test('keeps missing values last in either sort direction', () => {
  const rows = [row({ id: 1, original_amount: null }), row({ id: 2, original_amount: 50 }), row({ id: 3, original_amount: 20 })];
  assert.deepEqual(sortTransactions(rows, { key: 'original_amount', direction: 'asc' }).map((item) => item.id), [3, 2, 1]);
  assert.deepEqual(sortTransactions(rows, { key: 'original_amount', direction: 'desc' }).map((item) => item.id), [2, 3, 1]);
});

test('uses billing evidence before purchase-date fallback', () => {
  assert.equal(reportingValue(row({ billing_date: '2026-03-10' })), '2026-03-10');
  assert.equal(reportingValue(row({ billing_date: null, billing_month: '2026-04' })), '2026-04-01');
  assert.equal(reportingValue(row({ billing_date: null, billing_month: null, transaction_date: '2026-05-02' })), '2026-05-02');
  assert.equal(reportingSourceLabel('estimated'), 'Estimated installment month');
});

test('starts a new column ascending and toggles the active column', () => {
  assert.deepEqual(nextSort({ key: 'transaction_date', direction: 'desc' }, 'merchant'), { key: 'merchant', direction: 'asc' });
  assert.deepEqual(nextSort({ key: 'merchant', direction: 'asc' }, 'merchant'), { key: 'merchant', direction: 'desc' });
});
