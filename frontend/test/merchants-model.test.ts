import assert from 'node:assert/strict';
import test from 'node:test';
import type { MerchantRecord } from '../src/api/contracts.ts';
import { saveMerchant } from '../src/api/merchants.ts';
import { createMerchantDraft, filterMerchants, merchantDraftError, merchantImpact, merchantSaveRequest } from '../src/features/merchants/model.ts';

function merchant(overrides: Partial<MerchantRecord> = {}): MerchantRecord {
  return {
    canonical_group_id: 'coffee', display_name: 'Coffee', transactions: 4, amount: 100,
    last_seen: '2030-03-01', categories: ['Dining'], recurring_profile: null,
    aliases: [{ merchant_normalized: 'coffee a', merchant_raw: 'COFFEE A', category: 'Dining', subcategory: null, transactions: 4, recurring_included: false }],
    ...overrides,
  };
}

test('filters merchant identities by alias and review state', () => {
  const review = merchant({ canonical_group_id: 'review', display_name: 'Review', aliases: [{ merchant_normalized: 'branch', merchant_raw: 'BRANCH', category: 'Needs review', subcategory: null, transactions: 1, recurring_included: false }] });
  assert.deepEqual(filterMerchants([merchant(), review], 'branch', 'all').map((item) => item.display_name), ['Review']);
  assert.deepEqual(filterMerchants([merchant(), review], '', 'needs_review').map((item) => item.display_name), ['Review']);
});

test('saves only explicitly changed alias rules after impact review', () => {
  const draft = createMerchantDraft(merchant());
  draft.displayName = 'Coffee house';
  draft.aliases[0].category = 'Food';
  assert.equal(merchantDraftError(draft), '');
  assert.equal(merchantImpact(draft).length, 3);
  assert.deepEqual(merchantSaveRequest(draft), {
    canonical_group_id: 'coffee', display_name: 'Coffee house',
    aliases: [{ merchant_normalized: 'coffee a', category: 'Food', subcategory: '' }],
  });
});

test('rejects an unchanged or blank merchant draft', () => {
  const draft = createMerchantDraft(merchant());
  assert.equal(merchantDraftError(draft), 'No merchant changes to review.');
  draft.displayName = '';
  assert.equal(merchantDraftError(draft), 'Display name is required.');
});

test('posts reviewed display identity and alias decisions to merchant management', async () => {
  let body = '';
  globalThis.fetch = (async (_url: string | URL | Request, options: RequestInit = {}) => {
    body = String(options.body);
    return { ok: true, status: 200, json: async () => ({ status: 'saved', display_name: 'Coffee house', aliases_updated: 1, category_rules_updated: 1, transactions_updated: 4 }) } as Response;
  }) as typeof fetch;
  const request = { canonical_group_id: 'coffee', display_name: 'Coffee house', aliases: [{ merchant_normalized: 'coffee a', category: 'Food', subcategory: '' }] };
  const response = await saveMerchant(request);
  assert.equal(response.transactions_updated, 4);
  assert.equal(body, JSON.stringify(request));
});
