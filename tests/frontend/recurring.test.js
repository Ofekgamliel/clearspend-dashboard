const test = require('node:test');
const assert = require('node:assert/strict');

const {
  recurringCadenceOptions,
  recurringColumns,
  recurringStatusClass,
  recurringStatusLabels,
  recurringTypeOptions,
  sortedRecurringRows,
} = require('./legacy/recurring.js');

test('publishes the established recurring type and cadence choices', () => {
  assert.deepEqual(recurringTypeOptions, [
    'Fixed recurring',
    'Usage-based recurring',
    'Scheduled obligation',
    'Other recurring',
  ]);
  assert.equal(recurringCadenceOptions[0], 'Weekly');
  assert.equal(recurringCadenceOptions.at(-1), 'Unknown');
});

test('publishes the existing series and commitment table columns', () => {
  assert.deepEqual(recurringColumns.series[0], ['display_name', 'Merchant']);
  assert.deepEqual(recurringColumns.commitments[0], ['display_name', 'Purchase']);
  assert.equal(recurringColumns.series.at(-1)[0], 'status');
});

test('maps recurring statuses to their existing labels and visual classes', () => {
  assert.equal(recurringStatusLabels.increased, 'Increased');
  assert.equal(recurringStatusClass('missing'), 'amber');
  assert.equal(recurringStatusClass('completed'), 'gray');
  assert.equal(recurringStatusClass('confirmed'), '');
});

test('sorts recurring numeric fields numerically without mutating input', () => {
  const rows = [{ id: 1, remaining: 100 }, { id: 2, remaining: 9 }, { id: 3, remaining: 20 }];
  const original = [...rows];
  assert.deepEqual(sortedRecurringRows(rows, { key: 'remaining', direction: 'desc' }).map(row => row.id), [1, 3, 2]);
  assert.deepEqual(rows, original);
});

test('sorts text naturally and leaves missing values last in either direction', () => {
  const rows = [
    { id: 1, display_name: 'Plan 10' },
    { id: 2, display_name: null },
    { id: 3, display_name: 'Plan 2' },
  ];
  assert.deepEqual(sortedRecurringRows(rows, { key: 'display_name', direction: 'asc' }).map(row => row.id), [3, 1, 2]);
  assert.deepEqual(sortedRecurringRows(rows, { key: 'display_name', direction: 'desc' }).map(row => row.id), [1, 3, 2]);
});
