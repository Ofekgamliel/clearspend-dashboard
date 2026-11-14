import assert from 'node:assert/strict';
import test from 'node:test';
import {
  formatDate,
  formatInteger,
  formatMoney,
  formatMonth,
  formatPercent,
  formatShortMonth,
  formatSourceAmount,
} from '../src/shared/format.ts';

test('keeps the shekel symbol on the left in an English dashboard', () => {
  assert.equal(formatMoney(1234.5), '₪1,234.50');
  assert.equal(formatMoney(-1234.5), '-₪1,234.50');
  assert.equal(formatMoney(Number.NaN), '₪0.00');
});

test('preserves source currency codes without treating them as shekel totals', () => {
  assert.equal(formatSourceAmount(1234.5, 'USD'), '1,234.5 USD');
  assert.equal(formatSourceAmount(99, 'EUR'), '99 EUR');
  assert.equal(formatSourceAmount(-42.75, 'GBP'), '-42.75 GBP');
  assert.equal(formatSourceAmount(1000, 'JPY'), '1,000 JPY');
  assert.equal(formatSourceAmount(12.5, null), '12.5');
  assert.equal(formatSourceAmount(null, 'USD'), '—');
});

test('formats shared percentages, counts, dates, and month labels consistently', () => {
  assert.equal(formatPercent(12), '12%');
  assert.equal(formatPercent(12.34), '12.3%');
  assert.equal(formatInteger(1234.6), '1,235');
  assert.equal(formatDate('2026-11-08'), '8 Nov 26');
  assert.equal(formatMonth('2026-11'), 'November 2026');
  assert.equal(formatShortMonth('2026-11'), 'Nov 2026');
});
