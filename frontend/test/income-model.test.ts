import assert from 'node:assert/strict';
import test from 'node:test';
import type { IncomeSummary, ReportingPeriod } from '../src/api/contracts.ts';
import { averageRangeLabel, incomeAllocation, incomePeriodLabel } from '../src/features/income/model.ts';

function summary(overrides: Partial<IncomeSummary> = {}): IncomeSummary {
  return {
    has_income: true,
    income: 1000,
    spending: 400,
    charges: 400,
    refunds: 0,
    remaining: 600,
    remaining_percentage: 60,
    spent_percentage: 40,
    scope: 'all_cards',
    averages: {
      spending: 350,
      amount_left: 650,
      spending_months: 3,
      amount_left_months: 3,
      start_month: '2026-01',
      end_month: '2026-03',
      current_month_partial: false,
    },
    ...overrides,
  };
}

const monthPeriod: ReportingPeriod = {
  key: 'month',
  start: '2026-03-01',
  end: '2026-03-31',
  label: 'March 2026',
};

test('builds the income allocation from backend percentages', () => {
  assert.deepEqual(incomeAllocation(summary()), {
    spentWidth: 40,
    leftWidth: 60,
    spentLabel: '40% spent',
    leftLabel: '60% left',
    over: false,
    unavailable: false,
  });
});

test('bounds overspending visually without replacing the backend value', () => {
  assert.deepEqual(incomeAllocation(summary({
    spent_percentage: 125,
    remaining_percentage: -25,
  })), {
    spentWidth: 100,
    leftWidth: 0,
    spentLabel: '125% spent',
    leftLabel: '',
    over: true,
    unavailable: false,
  });
});

test('preserves the unavailable-income presentation', () => {
  const allocation = incomeAllocation(summary({
    has_income: false,
    remaining_percentage: null,
    spent_percentage: null,
  }));
  assert.equal(allocation.spentLabel, 'Income unavailable');
  assert.equal(allocation.unavailable, true);
});

test('labels partial months and the backend average range', () => {
  const partial = summary({
    averages: {
      ...summary().averages,
      current_month_partial: true,
    },
  });
  assert.equal(incomePeriodLabel(monthPeriod, partial), 'March 2026 · All cards · Partial month');
  assert.equal(averageRangeLabel(partial), 'Jan 2026 – Mar 2026 · Includes partial current month');
});
