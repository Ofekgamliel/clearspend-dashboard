const test = require('node:test');
const assert = require('node:assert/strict');

const {
  buildCategorySegments,
  categoryComparisonModel,
  categorySegmentAt,
  donutPercentageAt,
} = require('../../dist/categories.js');

test('builds ordered donut segments and fills an unused remainder', () => {
  const result = buildCategorySegments([
    { category: 'Food', share: 60 },
    { category: 'Travel', share: 25 },
  ], ['red', 'blue']);
  assert.deepEqual(result.segments.map(item => [item.start, item.end]), [[0, 60], [60, 85]]);
  assert.equal(result.gradient, 'conic-gradient(red 0% 60%,blue 60% 85%,#ececf1 85% 100%)');
  assert.equal(result.ariaLabel, 'Food: 60%, Travel: 25%');
});

test('caps donut segments at one hundred percent', () => {
  const result = buildCategorySegments([
    { category: 'A', share: 80 },
    { category: 'B', share: 30 },
  ], ['red', 'blue']);
  assert.deepEqual(result.segments.map(item => [item.start, item.end]), [[0, 80], [80, 100]]);
  assert.equal(result.gradient.includes('#ececf1'), false);
});

test('finds the segment containing a percentage with stable boundaries', () => {
  const segments = [{ category: 'A', start: 0, end: 60 }, { category: 'B', start: 60, end: 100 }];
  assert.equal(categorySegmentAt(segments, 59.99).category, 'A');
  assert.equal(categorySegmentAt(segments, 60).category, 'B');
  assert.equal(categorySegmentAt(segments, 100), undefined);
});

test('converts donut coordinates using the existing top-origin clockwise angle', () => {
  assert.equal(donutPercentageAt(0, -1), 0);
  assert.equal(donutPercentageAt(1, 0), 25);
  assert.equal(donutPercentageAt(0, 1), 50);
});

test('builds existing month-over-month labels and withholds them without a prior month', () => {
  assert.equal(categoryComparisonModel({ comparison: 'up', change_percent: -12.5 }, { previous_month: '2026-10' }).label, '↑ 12.5%');
  assert.equal(categoryComparisonModel({ comparison: 'down', change_percent: -8 }, { previous_month: '2026-10' }).label, '↓ 8%');
  assert.equal(categoryComparisonModel({ comparison: 'new' }, { previous_month: '2026-10' }).label, 'New');
  assert.equal(categoryComparisonModel({ comparison: 'same' }, null), null);
});
