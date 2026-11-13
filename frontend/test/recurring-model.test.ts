import assert from 'node:assert/strict';
import test from 'node:test';
import type { InstallmentCommitment, RecurringSeries } from '../src/api/contracts.ts';
import { recurringUrl } from '../src/api/recurring.ts';
import { burdenShares, nextRecurringSort, recurringStatusClass, recurringStatusLabels, sortRecurring } from '../src/features/recurring/model.ts';

const series = (overrides: Partial<RecurringSeries>): RecurringSeries => ({
  canonical_group_id: 'synthetic', display_name: 'Synthetic service', category: 'Services',
  recurring_type: 'Fixed recurring', cadence: 'Monthly', cadence_months: 1,
  lifecycle_status: 'active', end_month: null, source_aliases: ['Synthetic service'],
  series_id: 'synthetic\0Services', amount: 50, amount_kind: 'billed', coverage: 'Expected next month',
  status: 'confirmed', last_billed_month: '2030-02', billed_months: 2, typical_amount: 50, history: [],
  ...overrides,
});

const commitment = (overrides: Partial<InstallmentCommitment>): InstallmentCommitment => ({
  display_name: 'Synthetic purchase', source_alias: 'Synthetic purchase', category: 'Shopping',
  progress: '2 / 5', current_installment: 2, total_installments: 5, charge: 100,
  paid: 200, remaining: 300, remaining_count: 3, status: 'active', history: [], ...overrides,
});

test('builds the recurring query from shared dashboard filters', () => {
  const parsed = new URL(recurringUrl({ period: 'month', month: '2030-02', card: 'provider:1234' }), 'http://localhost');
  assert.equal(parsed.pathname, '/api/recurring');
  assert.equal(parsed.searchParams.get('month'), '2030-02');
  assert.equal(parsed.searchParams.get('card'), 'provider:1234');
});

test('bounds composition shares while preserving all three segments', () => {
  assert.deepEqual(burdenShares(20, 30), { recurring: 20, installments: 30, other: 50 });
  assert.deepEqual(burdenShares(85, 30), { recurring: 85, installments: 15, other: 0 });
});

test('maps statuses to established labels and visual states', () => {
  assert.equal(recurringStatusLabels.missing, 'Missing');
  assert.equal(recurringStatusClass('missing'), 'amber');
  assert.equal(recurringStatusClass('completed'), 'gray');
  assert.equal(recurringStatusClass('confirmed'), '');
});

test('sorts series and commitments without mutating API rows', () => {
  const seriesRows = [series({ series_id: 'b', display_name: 'Beta' }), series({ series_id: 'a', display_name: 'Alpha' })];
  const planRows = [commitment({ display_name: 'Small', remaining: 50 }), commitment({ display_name: 'Large', remaining: 500 })];
  assert.deepEqual(sortRecurring(seriesRows, { key: 'display_name', direction: 'asc' }).map((item) => item.display_name), ['Alpha', 'Beta']);
  assert.deepEqual(sortRecurring(planRows, { key: 'remaining', direction: 'desc' }).map((item) => item.remaining), [500, 50]);
  assert.equal(seriesRows[0]?.display_name, 'Beta');
});

test('starts a new recurring sort ascending and toggles the active sort', () => {
  assert.deepEqual(nextRecurringSort({ key: 'remaining', direction: 'desc' }, 'display_name'), { key: 'display_name', direction: 'asc' });
  assert.deepEqual(nextRecurringSort({ key: 'display_name', direction: 'asc' }, 'display_name'), { key: 'display_name', direction: 'desc' });
});
