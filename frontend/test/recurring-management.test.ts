import assert from 'node:assert/strict';
import test from 'node:test';
import type { MerchantRecord } from '../src/api/contracts.ts';
import { manageRecurringProfile } from '../src/api/merchants.ts';
import { filterRecurringMerchants, merchantRecurringVerdict, recurringManagementDraft, recurringManagementError, recurringManagementPayload } from '../src/features/recurring/management.ts';

function merchant(overrides: Partial<MerchantRecord> = {}): MerchantRecord {
  return {
    canonical_group_id: 'synthetic', display_name: 'Synthetic Mobile', transactions: 3,
    amount: 150, last_seen: '2030-03-01', categories: ['Communications'],
    aliases: [{ merchant_normalized: 'synthetic mobile', merchant_raw: 'SYNTHETIC MOBILE', category: 'Communications', subcategory: null, transactions: 3, recurring_included: false }],
    recurring_profile: null, ...overrides,
  };
}

test('filters recurring management by aliases and reviewed verdict', () => {
  const recurring = merchant({ canonical_group_id: 'one', recurring_profile: { canonical_group_id: 'one', verdict: 'recurring', recurring_type: 'Fixed recurring', cadence: 'Monthly', cadence_months: 1, lifecycle_status: 'active', end_month: null, updated_at: '2030-01-01', included_aliases: [] } });
  const unreviewed = merchant({ canonical_group_id: 'two', display_name: 'Other service', aliases: [{ merchant_normalized: 'hidden alias', merchant_raw: 'HIDDEN ALIAS', category: 'Other', subcategory: null, transactions: 1, recurring_included: false }] });
  assert.equal(merchantRecurringVerdict(recurring), 'recurring');
  assert.deepEqual(filterRecurringMerchants([recurring, unreviewed], 'hidden', 'all').map((item) => item.canonical_group_id), ['two']);
  assert.deepEqual(filterRecurringMerchants([recurring, unreviewed], '', 'recurring').map((item) => item.canonical_group_id), ['one']);
});

test('defaults a single unreviewed alias but validates explicit recurring scope', () => {
  const single = recurringManagementDraft(merchant());
  assert.deepEqual(single.included_aliases, ['synthetic mobile']);
  assert.equal(recurringManagementError({ ...single, included_aliases: [] }), 'Select at least one original merchant name.');
  assert.equal(recurringManagementError({ ...single, lifecycle_status: 'ended', end_month: '' }), 'Choose an end month for an ended profile.');
});

test('builds explicit add and removal decisions without changing transactions', () => {
  const item = merchant();
  const draft = recurringManagementDraft(item);
  assert.deepEqual(recurringManagementPayload(item, draft, 'recurring').included_aliases, ['synthetic mobile']);
  const removed = recurringManagementPayload(item, draft, 'not_recurring');
  assert.equal(removed.verdict, 'not_recurring');
  assert.deepEqual(removed.included_aliases, []);
});

test('posts recurring membership decisions to the dedicated management endpoint', async () => {
  let request: { url: string; options: RequestInit } | undefined;
  globalThis.fetch = (async (url: string | URL | Request, options: RequestInit = {}) => {
    request = { url: String(url), options };
    return { ok: true, status: 200, json: async () => ({
      canonical_group_id: 'synthetic', display_name: 'Synthetic Mobile', verdict: 'recurring',
      recurring_type: 'Fixed recurring', cadence: 'Monthly', cadence_months: 1,
      lifecycle_status: 'active', end_month: null, updated_at: '2030-03-01T10:00:00',
      included_aliases: ['synthetic mobile'],
    }) } as Response;
  }) as typeof fetch;
  const payload = recurringManagementPayload(merchant(), recurringManagementDraft(merchant()), 'recurring');
  const response = await manageRecurringProfile(payload);
  assert.equal(response.included_aliases[0], 'synthetic mobile');
  assert.equal(request?.url, '/api/recurring-profile/manage');
  assert.equal(request?.options.method, 'POST');
  assert.equal(request?.options.body, JSON.stringify(payload));
});
