const test = require('node:test');
const assert = require('node:assert/strict');

const {
  compact,
  escapeHtml,
  formatDate,
  formatDateTime,
  formatMonth,
  median,
  money,
  monthLabel,
  monthRange,
  shiftMonth,
} = require('../../dist/format.js');

test('escapes every HTML-significant character', () => {
  assert.equal(escapeHtml(`<a title="Tom & Jerry's">`), '&lt;a title=&quot;Tom &amp; Jerry&#39;s&quot;&gt;');
  assert.equal(escapeHtml(null), '');
});

test('formats money and compact numbers with the existing dashboard conventions', () => {
  assert.match(money(1234.5), /₪\s?1,234\.50|1,234\.50\s?₪/);
  assert.equal(compact(12500), '12.5K');
});

test('formats dates, date-times, and months consistently', () => {
  assert.equal(formatDate('2026-11-08'), '8 Nov 26');
  assert.match(formatDateTime('2026-11-08 14:05:00'), /^8 Nov 2026,? 14:05$/);
  assert.equal(formatMonth('2026-11'), 'November 2026');
  assert.equal(formatMonth(''), 'Latest month');
});

test('calculates medians after discarding non-numeric values', () => {
  assert.equal(median([5, '1', 9]), 5);
  assert.equal(median([1, 3, 5, 7]), 4);
  assert.equal(median(['not a number']), 0);
});

test('shifts and labels calendar months across year boundaries', () => {
  assert.equal(shiftMonth('2026-01', -1), '2025-12');
  assert.equal(shiftMonth('2026-11', 3), '2027-02');
  assert.equal(monthLabel('2026-11'), 'Nov 2026');
  assert.equal(monthRange(['2026-11', '2026-09', '2026-11']), 'Sept 2026 – Nov 2026');
  assert.equal(monthRange([]), '—');
});
