import assert from 'node:assert/strict';
import test from 'node:test';
import type { TransactionRow } from '../src/api/contracts.ts';
import { getMerchantReference } from '../src/api/merchants.ts';
import { saveTransactionAdjustment, saveTransactionCategory, saveTransactionEvent, transactionsUrl } from '../src/api/transactions.ts';
import { groupTransactionsByMerchant, nextMerchantGroupSort, nextSort, reportingSourceLabel, reportingValue, sortMerchantGroups, sortTransactions } from '../src/features/transactions/model.ts';

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

test('assigns an existing event through the established transaction endpoint', async () => {
  let request: { url: string; options: RequestInit } | undefined;
  globalThis.fetch = (async (url: string | URL | Request, options: RequestInit = {}) => {
    request = { url: String(url), options };
    return { ok: true, status: 200, json: async () => ({
      status: 'assigned', transaction_id: 7, merchant_raw: 'Synthetic merchant',
      event_id: 'event-3', event_name: 'Synthetic trip', event_type: 'trip', event_destination: null,
    }) } as Response;
  }) as typeof fetch;
  const response = await saveTransactionEvent({ transaction_id: 7, event_id: '3' });
  assert.equal(response.event_name, 'Synthetic trip');
  assert.equal(request?.url, '/api/transaction-event');
  assert.equal(request?.options.method, 'POST');
  assert.equal(request?.options.body, JSON.stringify({ transaction_id: 7, event_id: '3' }));
});

test('loads the permanent category vocabulary from merchant management', async () => {
  let requested = '';
  globalThis.fetch = (async (url: string | URL | Request) => {
    requested = String(url);
    return { ok: true, status: 200, json: async () => ({ categories: ['Food', 'Travel'] }) } as Response;
  }) as typeof fetch;
  assert.deepEqual((await getMerchantReference()).categories, ['Food', 'Travel']);
  assert.equal(requested, '/api/merchants');
});

test('saves a one-off category correction without changing the merchant rule', async () => {
  let request: { url: string; options: RequestInit } | undefined;
  globalThis.fetch = (async (url: string | URL | Request, options: RequestInit = {}) => {
    request = { url: String(url), options };
    return { ok: true, status: 200, json: async () => ({
      status: 'saved', transaction_id: 7, merchant_raw: 'Synthetic merchant', category: 'Travel', subcategory: null,
    }) } as Response;
  }) as typeof fetch;
  const response = await saveTransactionCategory({ transaction_id: 7, category: 'Travel', subcategory: '' });
  assert.equal(response.category, 'Travel');
  assert.equal(request?.url, '/api/transaction-category');
  assert.equal(request?.options.method, 'POST');
  assert.equal(request?.options.body, JSON.stringify({ transaction_id: 7, category: 'Travel', subcategory: '' }));
});

test('saves a reviewed reimbursement while preserving the original charge', async () => {
  let body = '';
  globalThis.fetch = (async (_url: string | URL | Request, options: RequestInit = {}) => {
    body = String(options.body);
    return { ok: true, status: 200, json: async () => ({
      status: 'saved', transaction_id: 7, merchant_raw: 'Synthetic merchant',
      adjustment_type: 'partial_reimbursement', reimbursed_amount: 60, personal_amount: 40,
    }) } as Response;
  }) as typeof fetch;
  const response = await saveTransactionAdjustment({
    transaction_id: 7, remove: false, reimbursed_amount: 60,
    reimbursement_date: '2030-03-05', note: 'Synthetic reimbursement',
  });
  assert.equal(response.personal_amount, 40);
  assert.equal(body, JSON.stringify({ transaction_id: 7, remove: false, reimbursed_amount: 60, reimbursement_date: '2030-03-05', note: 'Synthetic reimbursement' }));
});

test('removes only the reviewed reimbursement adjustment', async () => {
  let body = '';
  globalThis.fetch = (async (_url: string | URL | Request, options: RequestInit = {}) => {
    body = String(options.body);
    return { ok: true, status: 200, json: async () => ({
      status: 'removed', transaction_id: 7, merchant_raw: 'Synthetic merchant', personal_amount: 100,
    }) } as Response;
  }) as typeof fetch;
  await saveTransactionAdjustment({ transaction_id: 7, remove: true });
  assert.equal(body, JSON.stringify({ transaction_id: 7, remove: true }));
});

test('groups category transactions by display identity and personal amount', () => {
  const rows = [
    row({ id: 1, canonical_merchant_id: 'coffee', merchant_display_name: 'Coffee', merchant_raw: 'COFFEE A', transaction_date: '2030-03-01', amount: 20, personal_amount: 20 }),
    row({ id: 2, canonical_merchant_id: 'coffee', merchant_display_name: 'Coffee', merchant_raw: 'COFFEE B', transaction_date: '2030-03-05', amount: 30, personal_amount: 10 }),
    row({ id: 3, canonical_merchant_id: 'market', merchant_display_name: 'Market', transaction_date: '2030-03-03', amount: 40, personal_amount: 40 }),
  ];
  const groups = groupTransactionsByMerchant(rows);
  const coffee = groups.find((item) => item.key === 'coffee');
  assert.equal(coffee?.count, 2);
  assert.equal(coffee?.amount, 30);
  assert.equal(coffee?.latest_date, '2030-03-05');
  assert.deepEqual(coffee?.aliases, ['COFFEE A', 'COFFEE B']);
});

test('sorts collapsed merchant groups without mutating them', () => {
  const groups = groupTransactionsByMerchant([
    row({ id: 1, canonical_merchant_id: 'b', merchant_display_name: 'Beta', personal_amount: 20 }),
    row({ id: 2, canonical_merchant_id: 'a', merchant_display_name: 'Alpha', personal_amount: 50 }),
  ]);
  assert.deepEqual(sortMerchantGroups(groups, { key: 'amount', direction: 'desc' }).map((item) => item.display_name), ['Alpha', 'Beta']);
  assert.deepEqual(nextMerchantGroupSort({ key: 'latest_date', direction: 'desc' }, 'merchant'), { key: 'merchant', direction: 'asc' });
});
