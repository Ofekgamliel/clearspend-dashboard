import assert from 'node:assert/strict';
import test from 'node:test';
import { dashboardUrl } from '../src/api/dashboard.ts';
import { cardLabel, normalizeAvailableMonths, selectedMonth } from '../src/features/filters/model.ts';

test('builds the existing dashboard filter query without dropping an empty month', () => {
  assert.equal(
    dashboardUrl({ period: 'month', month: '', card: 'all' }),
    '/api/dashboard?period=month&month=&card=all',
  );
  assert.equal(
    dashboardUrl({ period: 'year', month: '2026-09', card: 'max:1234' }),
    '/api/dashboard?period=year&month=2026-09&card=max%3A1234',
  );
});

test('normalizes imported months and resolves the selected fallback deterministically', () => {
  const months = ['2026-08', 'bad', '2026-10', '2026-08', '2026-09'];
  assert.deepEqual(normalizeAvailableMonths(months), ['2026-10', '2026-09', '2026-08']);
  assert.equal(selectedMonth('2026-09', '2026-10-01', months), '2026-09');
  assert.equal(selectedMonth('', '2026-08-01', months), '2026-08');
  assert.equal(selectedMonth('', null, months), '2026-10');
});

test('uses the established compact card identity label', () => {
  assert.equal(cardLabel(undefined), 'All cards');
  assert.equal(cardLabel({
    key: 'provider:1234',
    provider: 'provider',
    product_name: 'Synthetic card',
    card_last4: '1234',
    amount: 0,
    share: 0,
    transactions: 0,
  }), 'Synthetic card •• 1234');
});
