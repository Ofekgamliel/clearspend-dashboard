const test = require('node:test');
const assert = require('node:assert/strict');

const {
  buildEventPanelItems,
  destinationKey,
  eventDateValidationMessage,
  isBusinessTrip,
} = require('../../dist/events.js');

const event = (id, startDate, options = {}) => ({
  id,
  start_date: startDate,
  event_type: options.type || 'trip',
  destination: options.destination || '',
});

test('recognizes the established business-trip type and normalizes destination keys', () => {
  assert.equal(isBusinessTrip('business_trip'), true);
  assert.equal(isBusinessTrip('trip'), false);
  assert.equal(destinationKey('  North District  '), 'north district');
});

test('preserves the existing event date validation message', () => {
  assert.equal(eventDateValidationMessage({ start_date: '2026-11-10', end_date: '2026-11-09' }), 'End date cannot be before the start date.');
  assert.equal(eventDateValidationMessage({ start_date: '2026-11-10', end_date: '2026-11-10' }), '');
});

test('does not group repeated business trips in a monthly view', () => {
  const events = [
    event('a', '2026-11-01', { type: 'business_trip', destination: 'North' }),
    event('b', '2026-11-08', { type: 'business_trip', destination: 'North' }),
  ];
  const result = buildEventPanelItems(events, 'month');
  assert.equal(result.groups.size, 0);
  assert.deepEqual(result.items.map(item => item.event.id), ['b', 'a']);
});

test('groups repeated business destinations outside the monthly view', () => {
  const events = [
    event('a', '2026-01-10', { type: 'business_trip', destination: 'North' }),
    event('b', '2026-05-12', { type: 'business_trip', destination: ' north ' }),
    event('c', '2026-07-01', { type: 'business_trip', destination: 'South' }),
    event('d', '2026-09-01'),
  ];
  const result = buildEventPanelItems(events, 'year');
  assert.equal(result.groups.size, 1);
  assert.deepEqual([...result.groups.values()][0].map(item => item.id), ['a', 'b']);
  assert.deepEqual(result.items.map(item => item.kind), ['event', 'event', 'group']);
  assert.equal(result.items.at(-1).start_date, '2026-01-10');
});

test('leaves a single business destination as an ordinary event card', () => {
  const only = event('a', '2026-01-10', { type: 'business_trip', destination: 'North' });
  const result = buildEventPanelItems([only], 'all');
  assert.equal(result.groups.size, 0);
  assert.equal(result.items[0].event, only);
});
