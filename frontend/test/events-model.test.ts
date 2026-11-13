import assert from 'node:assert/strict';
import test from 'node:test';
import type { EventSummary } from '../src/api/contracts.ts';
import { eventsUrl } from '../src/api/events.ts';
import { buildEventPanelItems, categoryTotals, destinationKey, eventIcon, isBusinessTrip } from '../src/features/events/model.ts';

function event(id: number, start: string, overrides: Partial<EventSummary> = {}): EventSummary {
  return {
    id, name: `Synthetic event ${id}`, event_type: 'trip', destination: null, icon: 'plane',
    start_date: start, end_date: start, status: 'completed', budget: null, notes: null,
    transactions: [], transaction_count: 0, amount: 0, total_transaction_count: 0,
    total_amount: 0, category_count: 0, card_count: 0, ...overrides,
  };
}

test('builds the events query from shared filters', () => {
  const parsed = new URL(eventsUrl({ period: 'year', month: '2030-02', card: 'provider:1234' }), 'http://localhost');
  assert.equal(parsed.pathname, '/api/events');
  assert.equal(parsed.searchParams.get('period'), 'year');
  assert.equal(parsed.searchParams.get('card'), 'provider:1234');
});

test('groups repeated business destinations only in longer periods', () => {
  const events = [
    event(1, '2030-01-01', { event_type: 'business_trip', destination: 'North' }),
    event(2, '2030-02-01', { event_type: 'business_trip', destination: ' north ' }),
  ];
  assert.deepEqual(buildEventPanelItems(events, 'month').map((item) => item.kind), ['event', 'event']);
  const annual = buildEventPanelItems(events, 'year');
  assert.equal(annual.length, 1);
  assert.equal(annual[0]?.kind, 'group');
});

test('keeps event cards ordered newest first', () => {
  const items = buildEventPanelItems([event(1, '2030-01-01'), event(2, '2030-04-01')], 'month');
  assert.equal(items[0]?.kind === 'event' ? items[0].event.id : null, 2);
});

test('aggregates event category amounts from exact transaction membership', () => {
  const totals = categoryTotals([
    { id: 1, merchant_raw: 'A', merchant_display_name: 'A', category: 'Food', transaction_date: '2030-01-01', provider: 'p', card_last4: '1', amount: 10, personal_amount: 10 },
    { id: 2, merchant_raw: 'B', merchant_display_name: 'B', category: 'Food', transaction_date: '2030-01-02', provider: 'p', card_last4: '1', amount: 20, personal_amount: 20 },
    { id: 3, merchant_raw: 'C', merchant_display_name: 'C', category: 'Travel', transaction_date: '2030-01-03', provider: 'p', card_last4: '1', amount: 50, personal_amount: 50 },
  ]);
  assert.deepEqual(totals, [{ category: 'Travel', amount: 50 }, { category: 'Food', amount: 30 }]);
});

test('preserves business identity and established icon fallbacks', () => {
  assert.equal(isBusinessTrip('business_trip'), true);
  assert.equal(destinationKey(' NORTH '), 'north');
  assert.equal(eventIcon(event(1, '2030-01-01', { event_type: 'business_trip' })), 'briefcase');
  assert.equal(eventIcon(event(2, '2030-01-01', { icon: 'sun' })), '☀');
});
