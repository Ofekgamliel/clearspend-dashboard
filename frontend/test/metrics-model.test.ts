import assert from 'node:assert/strict';
import test from 'node:test';
import { metricContext } from '../src/features/metrics/model.ts';

test('builds metric context without recalculating backend amounts', () => {
  assert.deepEqual(metricContext({
    spent: 1250,
    refunds: 50,
    transactions: 1234,
    daily_average: 75,
    active_days: 17,
  }), {
    transactionNote: 'Calculated from 1,234 imported transactions',
    activeDaysNote: 'across 17 active days',
  });
});

test('keeps empty-period metric labels explicit', () => {
  assert.deepEqual(metricContext({
    spent: 0,
    refunds: 0,
    transactions: 0,
    daily_average: 0,
    active_days: 0,
  }), {
    transactionNote: 'Calculated from 0 imported transactions',
    activeDaysNote: 'across 0 active days',
  });
});
