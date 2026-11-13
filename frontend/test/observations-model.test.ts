import assert from 'node:assert/strict';
import test from 'node:test';
import type { ObservationsResponse } from '../src/api/contracts.ts';
import { observationsUrl, saveObservationReview } from '../src/api/observations.ts';
import { observationActivity, observationCount, observationMetricLabels, observationReviewOption, observationReviewRequest, observationScope, observationVisual } from '../src/features/observations/model.ts';

const response: ObservationsResponse = {
  period: 'year', selectedCard: 'all', selectedMonth: '2026-01',
  observedStart: '2026-01', observedEnd: '2026-11', historical: true,
  findingCount: 7, typeCount: 3, findings: [], groups: [],
};

test('builds the typed observation URL with income privacy', () => {
  const parsed = new URL(observationsUrl({ period: 'all', month: '2026-11', card: 'provider:1234', incomeHidden: true }), 'http://localhost');
  assert.equal(parsed.pathname, '/api/observations');
  assert.equal(parsed.searchParams.get('period'), 'all');
  assert.equal(parsed.searchParams.get('card'), 'provider:1234');
  assert.equal(parsed.searchParams.get('income_hidden'), 'true');
});

test('formats historical observation count and scope from backend metadata', () => {
  assert.equal(observationCount(response), '7 PATTERNS · 3 TYPES');
  assert.equal(observationScope(response), 'Jan 2026 – Nov 2026 · all cards · lasting shifts that began during this period');
});

test('preserves established visual identity and metric-label overrides', () => {
  assert.deepEqual(observationVisual('POSSIBLE DUPLICATE'), { icon: '≡', color: '#6658e8', priority: true });
  assert.deepEqual(observationMetricLabels({
    type: 'LARGE PURCHASE', month: '2026-11', label: 'A', title: 'A', description: '', score: 1,
    value: '₪500', evidence: [], comparisonLabel: 'Custom baseline',
  }), ['Personal amount', 'Custom baseline', 'Share of month']);
});

test('allows resolution only for the three reviewed observation types', () => {
  assert.equal(observationReviewOption('LARGE PURCHASE'), null);
  assert.equal(observationReviewOption('POSSIBLE DUPLICATE')?.action, 'Not duplicate');
  assert.equal(observationReviewOption('ADDITIONAL RECURRING CHARGE')?.resolution, 'expected_charge');
  assert.equal(observationReviewOption('UNUSUAL TRANSACTION')?.resolved, 'Marked as expected / not unusual');
});

test('builds the established reversible review payload without changing facts', () => {
  assert.deepEqual(observationReviewRequest({
    type: 'POSSIBLE DUPLICATE', month: '2026-11', label: 'Store', title: 'Match', description: '',
    score: 1, value: '₪25', evidence: [], findingKey: 'POSSIBLE DUPLICATE:2,3', transactionIds: [2, 3],
  }), {
    finding_key: 'POSSIBLE DUPLICATE:2,3', observation_type: 'POSSIBLE DUPLICATE', resolution: 'not_duplicate',
    month: '2026-11', transaction_ids: [2, 3], recurring_series_id: '', occurrence_start: '',
    occurrence_end: '', merchant_label: 'Store', remove: false,
  });
  assert.equal(observationReviewRequest({
    type: 'LARGE PURCHASE', month: '2026-11', label: 'Store', title: 'Large', description: '',
    score: 1, value: '₪500', evidence: [],
  }), null);
});

test('posts reversible reviews to the dedicated endpoint', async () => {
  let request: { url: string; options: RequestInit } | undefined;
  globalThis.fetch = (async (url: string | URL | Request, options: RequestInit = {}) => {
    request = { url: String(url), options };
    return { ok: true, status: 200, json: async () => ({ status: 'reviewed', finding_key: 'UNUSUAL TRANSACTION:7' }) } as Response;
  }) as typeof fetch;
  await saveObservationReview({
    finding_key: 'UNUSUAL TRANSACTION:7', observation_type: 'UNUSUAL TRANSACTION', resolution: 'not_unusual',
    month: '2026-11', transaction_ids: [7], recurring_series_id: '', occurrence_start: '',
    occurrence_end: '', merchant_label: 'Store', remove: false,
  });
  assert.equal(request?.url, '/api/observation-review');
  assert.equal(request?.options.method, 'POST');
  assert.equal(request?.options.body, JSON.stringify({
    finding_key: 'UNUSUAL TRANSACTION:7', observation_type: 'UNUSUAL TRANSACTION', resolution: 'not_unusual',
    month: '2026-11', transaction_ids: [7], recurring_series_id: '', occurrence_start: '',
    occurrence_end: '', merchant_label: 'Store', remove: false,
  }));
});

test('routes observation activity without duplicating feature modals', () => {
  const base = { month: '2026-11', title: '', description: '', score: 1, value: '', evidence: [] };
  assert.deepEqual(observationActivity({ ...base, type: 'AMOUNT LEFT TREND', label: 'Household' }), { target: 'income', label: 'View income & spending' });
  assert.deepEqual(observationActivity({ ...base, type: 'CATEGORY ROUTINE SHIFTED', label: 'Food' }), { target: 'transactions', label: 'Open category activity', category: 'Food', routine: true });
  assert.deepEqual(observationActivity({ ...base, type: 'POSSIBLE DUPLICATE', label: 'Store', transactionIds: [2, 3] }), { target: 'transactions', label: 'Open transactions', transactionIds: [2, 3] });
  assert.deepEqual(observationActivity({ ...base, type: 'ADDITIONAL RECURRING CHARGE', label: 'Service', recurringSeriesId: 'series-1' }), { target: 'recurring', label: 'Open recurring series', recurringSeriesId: 'series-1', recurringTab: 'series' });
  assert.deepEqual(observationActivity({ ...base, type: 'PERSISTENT INSTALLMENT BURDEN', label: 'Plans' }), { target: 'recurring', label: 'Open installment commitments', recurringTab: 'commitments' });
});
