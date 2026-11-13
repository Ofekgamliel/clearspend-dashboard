import assert from 'node:assert/strict';
import test from 'node:test';
import type { CategoryRow } from '../src/api/contracts.ts';
import {
  buildCategorySegments,
  categoryComparisonModel,
} from '../src/features/categories/model.ts';

function category(overrides: Partial<CategoryRow>): CategoryRow {
  return {
    category: 'Synthetic category',
    amount: 240,
    transactions: 3,
    merchants: 2,
    share: 60,
    ...overrides,
  };
}

test('builds the preview donut from backend-owned shares', () => {
  const model = buildCategorySegments([
    category({ category: 'One', share: 60 }),
    category({ category: 'Two', share: 25 }),
  ], ['#111111', '#222222']);

  assert.deepEqual(model.segments.map(({ category: name, start, end, color }) => ({
    name,
    start,
    end,
    color,
  })), [
    { name: 'One', start: 0, end: 60, color: '#111111' },
    { name: 'Two', start: 60, end: 85, color: '#222222' },
  ]);
  assert.match(model.gradient, /#ececf1 85% 100%/);
  assert.equal(model.ariaLabel, 'One: 60%, Two: 25%');
});

test('preserves the established previous-month comparison labels', () => {
  const comparison = { available: true, previous_month: '2026-09' };
  assert.deepEqual(
    categoryComparisonModel(category({ comparison: 'up', change_percent: 12.5 }), comparison),
    { label: '↑ 12.5%', previousMonth: '2026-09', status: 'up' },
  );
  assert.equal(
    categoryComparisonModel(category({ comparison: 'new' }), comparison)?.label,
    'New',
  );
  assert.equal(
    categoryComparisonModel(category({}), { available: false, previous_month: null }),
    null,
  );
});
