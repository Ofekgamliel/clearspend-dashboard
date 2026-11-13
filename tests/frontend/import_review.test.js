const test = require('node:test');
const assert = require('node:assert/strict');

const {
  importPreviewIdentity,
  importPreviewRows,
  importPreviewStatus,
  importStepNames,
  invalidMerchantDecisions,
  manualReconciliationFiles,
  merchantDecision,
  requiresManualReconciliation,
  unresolvedDuplicateDecisions,
} = require('./legacy/import-review.js');

test('publishes the existing five staged-import steps', () => {
  assert.deepEqual(importStepNames, ['Files', 'Checks', 'Merchants', 'Reconcile', 'Approve']);
});

test('requires reconciliation only for ready statements with manual or mismatched totals', () => {
  const files = [
    { filename: 'a', kind: 'statement', status: 'ready', reconciliation: { status: 'manual_required' } },
    { filename: 'b', kind: 'statement', status: 'ready', reconciliation: { status: 'mismatch' } },
    { filename: 'c', kind: 'statement', status: 'ready', reconciliation: { status: 'matched' } },
    { filename: 'd', kind: 'income', status: 'ready', reconciliation: { status: 'manual_required' } },
  ];
  assert.deepEqual(manualReconciliationFiles(files).map(file => file.filename), ['a', 'b']);
  assert.equal(requiresManualReconciliation(files[0]), true);
  assert.equal(requiresManualReconciliation(files[2]), false);
});

test('identifies incomplete permanent merchant and duplicate decisions', () => {
  const merchantDecisions = new Map([
    ['valid', { resolution: 'create', category: 'Food' }],
    ['deferred', { resolution: 'needs_review', category: 'Needs review' }],
    ['bad-category', { resolution: 'create', category: 'Needs review' }],
    ['bad-link', { resolution: 'link', category: 'Food', canonical_group_id: '' }],
  ]);
  assert.deepEqual(invalidMerchantDecisions(merchantDecisions).map(item => item.resolution), ['create', 'link']);
  const possible = [{ candidate_id: 'a' }, { candidate_id: 'b' }, { candidate_id: 'c' }];
  const duplicateDecisions = new Map([['a', 'skip'], ['b', 'import']]);
  assert.deepEqual(unresolvedDuplicateDecisions(possible, duplicateDecisions), [{ candidate_id: 'c' }]);
});

test('builds the established suggested, provider, and deferred merchant decisions', () => {
  const merchant = { merchant_normalized: 'shop', merchant_raw: 'Shop', display_name: 'Shop' };
  const suggestion = {
    category_status: 'unanimous', category: 'Food', display_name: 'Known Shop', canonical_group_id: 'group-1',
  };
  assert.deepEqual(merchantDecision(merchant, suggestion), {
    merchant_normalized: 'shop', resolution: 'link', category: 'Food', display_name: 'Known Shop',
    canonical_group_id: 'group-1', scope: 'exact', suggested_match: true,
  });
  assert.equal(merchantDecision({ ...merchant, provider_category: 'Travel' }).resolution, 'provider');
  assert.equal(merchantDecision(merchant).resolution, 'needs_review');
});

test('builds the read-only import preview after exclusion and duplicate review', () => {
  const batch = {
    new_transactions: [
      { id: 1, merchant: 'Included', merchant_normalized: 'included', transaction_date: '2026-11-01' },
      { id: 2, merchant: 'Excluded', merchant_normalized: 'excluded', transaction_date: '2026-11-03' },
    ],
    possible_duplicates: [
      { candidate_id: 'candidate', merchant: 'Reviewed', merchant_normalized: 'included', transaction_date: '2026-11-02' },
    ],
  };
  const decisions = new Map([['excluded', { merchant_normalized: 'excluded', resolution: 'exclude' }]]);
  const duplicateDecisions = new Map([['candidate', 'import']]);
  const rows = importPreviewRows(batch, decisions, duplicateDecisions);
  assert.deepEqual(rows.map(row => row.merchant), ['Reviewed', 'Included']);
  assert.equal(rows[0].reviewed_new, true);
});

test('resolves preview identity and preserves status-label precedence', () => {
  const row = { merchant: 'Raw', merchant_normalized: 'raw', reviewed_new: true, source_status: 'pending' };
  const decisions = new Map([['raw', { display_name: 'Display', category: 'Food' }]]);
  assert.deepEqual(importPreviewIdentity(row, decisions, []), { display: 'Display', category: 'Food' });
  assert.deepEqual(importPreviewStatus(row), ['Reviewed as new', 'amber']);
  assert.deepEqual(importPreviewStatus({ source_status: 'outside_cycle' }), ['Outside billing cycle', 'purple']);
  assert.deepEqual(importPreviewStatus({ installment_number: 2, installment_total: 5 }), ['Installment 2/5', 'purple']);
  assert.deepEqual(importPreviewStatus({}), ['Confirmed new', '']);
});
