const test = require('node:test');
const assert = require('node:assert/strict');

const {
  sortedTransactionRows,
  transactionColumns,
  transactionSortValue,
} = require('./legacy/transactions.js');

test('publishes the existing transaction table columns in their established order', () => {
  assert.deepEqual(transactionColumns.slice(0, 3), [
    ['merchant', 'Merchant'],
    ['category', 'Category / subcategory'],
    ['card', 'Provider / card / source'],
  ]);
  assert.equal(transactionColumns.at(-1)[0], 'notes');
});

test('builds composite values for merchant, category, and card sorting', () => {
  const row = {
    merchant_display_name: 'Display',
    merchant_raw: 'Statement',
    merchant_normalized: 'statement',
    category: 'Food',
    subcategory: 'Cafe',
    provider: 'issuer',
    card_last4: '1234',
    source_sheet: 'Sheet 1',
  };
  assert.equal(transactionSortValue(row, 'merchant'), 'Display Statement statement');
  assert.equal(transactionSortValue(row, 'category'), 'Food Cafe');
  assert.equal(transactionSortValue(row, 'card'), 'issuer 1234 Sheet 1');
});

test('sorts numeric transaction fields numerically and does not mutate input', () => {
  const rows = [{ id: 1, amount: 100 }, { id: 2, amount: 9 }, { id: 3, amount: 20 }];
  const original = [...rows];
  assert.deepEqual(sortedTransactionRows(rows, { key: 'amount', direction: 'asc' }).map(row => row.id), [2, 3, 1]);
  assert.deepEqual(rows, original);
});

test('sorts transaction dates in either direction', () => {
  const rows = [
    { id: 1, transaction_date: '2026-01-02' },
    { id: 2, transaction_date: '2025-12-31' },
    { id: 3, transaction_date: '2026-11-08' },
  ];
  assert.deepEqual(sortedTransactionRows(rows, { key: 'transaction_date', direction: 'asc' }).map(row => row.id), [2, 1, 3]);
  assert.deepEqual(sortedTransactionRows(rows, { key: 'transaction_date', direction: 'desc' }).map(row => row.id), [3, 1, 2]);
});

test('keeps missing values at the end for ascending and descending sorts', () => {
  const rows = [{ id: 1, billing_date: null }, { id: 2, billing_date: '2026-01-01' }];
  assert.deepEqual(sortedTransactionRows(rows, { key: 'billing_date', direction: 'asc' }).map(row => row.id), [2, 1]);
  assert.deepEqual(sortedTransactionRows(rows, { key: 'billing_date', direction: 'desc' }).map(row => row.id), [2, 1]);
});
