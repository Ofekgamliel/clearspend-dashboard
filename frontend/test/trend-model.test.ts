import assert from 'node:assert/strict';
import test from 'node:test';
import type { CategoryRow, ReportingPeriod } from '../src/api/contracts.ts';
import { axisValues, buildBillingTrend, buildMonthlyTrend } from '../src/features/trend/model.ts';

const period: ReportingPeriod = {
  key: 'month',
  start: '2026-03-01',
  end: '2026-03-03',
  label: 'March 2026',
};
const categories: CategoryRow[] = [{
  category: 'Food', amount: 80, transactions: 2, merchants: 1, share: 100,
}];

test('fills missing calendar days and builds category stacks and cumulative values', () => {
  const model = buildMonthlyTrend([
    { bucket: '2026-03-01', amount: 100, categories: [{ category: 'Food', amount: 100 }] },
    { bucket: '2026-03-03', amount: -20, categories: [{ category: 'Food', amount: -20 }] },
  ], categories, period, new Date('2026-04-01T12:00:00Z'));

  assert.equal(model.days.length, 3);
  assert.deepEqual(model.days.map((day) => day.amount), [100, 0, -20]);
  assert.deepEqual(model.days.map((day) => day.cumulative), [100, 100, 80]);
  assert.equal(model.days[0]?.segments.length, 1);
  assert.equal(model.days[2]?.refunds, 20);
  assert.match(model.path, /^M/);
});

test('builds grouped billing bars with optional income', () => {
  const points = [
    { bucket: '2026-01', amount: 400, income: 1000 },
    { bucket: '2026-02', amount: 600, income: 1000 },
  ];
  const withIncome = buildBillingTrend(points, true);
  const spendingOnly = buildBillingTrend(points, false);
  assert.equal(withIncome.showIncome, true);
  assert.equal(withIncome.max, 1000);
  assert.equal(withIncome.bars.length, 2);
  assert.equal(spendingOnly.max, 600);
  assert.equal(spendingOnly.showIncome, false);
});

test('provides the five established chart-axis values', () => {
  assert.deepEqual(axisValues(100), [100, 75, 50, 25, 0]);
});
