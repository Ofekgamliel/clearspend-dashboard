import type { DisplayIdentityReference, ImportMerchantDecision, StagedFile, StagedImportBatch, StagedMerchant, StagedTransaction } from '../../api/contracts.ts';

export const importSteps = ['Files', 'Checks', 'Merchants', 'Reconcile', 'Approve'] as const;
export type DuplicateAction = 'skip' | 'import';

function normalize(value: string): string { return value.normalize('NFKD').toLocaleLowerCase().replace(/[\u0591-\u05c7]/g, '').replace(/[^\p{L}\p{N}]+/gu, ' ').replace(/\b\d+\b/g, ' ').replace(/\s+/g, ' ').trim(); }
export function displayMatchScore(query: string, candidate: string): number {
  const wanted = normalize(query); const existing = normalize(candidate);
  if (!wanted) return 1; if (!existing) return 0; if (wanted === existing) return 100;
  if (wanted.includes(existing) || existing.includes(wanted)) return 80 + Math.min(existing.length, wanted.length) / Math.max(existing.length, wanted.length) * 10;
  const a = new Set(wanted.split(' ')); const b = new Set(existing.split(' ')); const overlap = [...a].filter((item) => b.has(item)).length;
  return overlap ? overlap / a.size * 55 + overlap / b.size * 25 : 0;
}
export function rankedIdentities(query: string, identities: DisplayIdentityReference[]): DisplayIdentityReference[] {
  return identities.map((item) => ({ item, score: Math.max(displayMatchScore(query, item.display_name), ...item.alias_names.map((alias) => displayMatchScore(query, alias))) }))
    .filter((entry) => !query.trim() || entry.score > 0).sort((a, b) => b.score - a.score || b.item.transactions - a.item.transactions).map((entry) => entry.item);
}
export function strongIdentity(query: string, identities: DisplayIdentityReference[]): DisplayIdentityReference | null {
  const ranked = identities.map((item) => ({ item, score: Math.max(displayMatchScore(query, item.display_name), ...item.alias_names.map((alias) => displayMatchScore(query, alias))) })).sort((a, b) => b.score - a.score);
  return ranked[0] && ranked[0].score >= 80 && (!ranked[1] || ranked[0].score - ranked[1].score >= 20) ? ranked[0].item : null;
}
export function initialDecision(merchant: StagedMerchant, identities: DisplayIdentityReference[]): ImportMerchantDecision {
  const suggestion = strongIdentity(merchant.merchant_raw, identities);
  if (suggestion) return { merchant_normalized: merchant.merchant_normalized, resolution: 'link', category: suggestion.category_status === 'unanimous' ? suggestion.category! : 'Needs review', display_name: suggestion.display_name, canonical_group_id: suggestion.canonical_group_id, scope: 'exact', suggested_match: true };
  return { merchant_normalized: merchant.merchant_normalized, resolution: merchant.provider_category ? 'provider' : 'needs_review', category: merchant.provider_category || 'Needs review', display_name: merchant.display_name || merchant.merchant_raw, canonical_group_id: merchant.canonical_group_id || '', scope: merchant.provider_category ? 'exact' : 'batch' };
}
export function needsReconciliation(file: StagedFile): boolean { return file.kind === 'statement' && file.status === 'ready' && ['manual_required', 'mismatch'].includes(file.reconciliation?.status ?? ''); }
export function invalidDecisions(decisions: ImportMerchantDecision[]): ImportMerchantDecision[] { return decisions.filter((item) => !['needs_review', 'exclude'].includes(item.resolution) && (!item.category || item.category === 'Needs review' || (item.resolution === 'link' && !item.canonical_group_id))); }
export function unresolvedDuplicates(batch: StagedImportBatch, decisions: Map<string, DuplicateAction>): StagedTransaction[] { return batch.possible_duplicates.filter((item) => !decisions.has(item.candidate_id ?? '')); }
export function previewRows(batch: StagedImportBatch, decisions: Map<string, ImportMerchantDecision>, duplicates: Map<string, DuplicateAction>): StagedTransaction[] {
  const excluded = new Set([...decisions.values()].filter((item) => item.resolution === 'exclude').map((item) => item.merchant_normalized));
  return [...batch.new_transactions.filter((row) => !excluded.has(row.merchant_normalized)), ...batch.possible_duplicates.filter((row) => duplicates.get(row.candidate_id ?? '') === 'import' && !excluded.has(row.merchant_normalized)).map((row) => ({ ...row, reviewed_new: true }))]
    .sort((a, b) => String(b.billing_date || b.transaction_date || '').localeCompare(String(a.billing_date || a.transaction_date || '')));
}
export function canContinue(step: number, batch: StagedImportBatch | null, merchantDecisions: Map<string, ImportMerchantDecision>, duplicates: Map<string, DuplicateAction>, reconciled: Set<string>): boolean {
  if (!batch || step === 0) return false;
  if (step === 1) return unresolvedDuplicates(batch, duplicates).length === 0;
  if (step === 2) return invalidDecisions([...merchantDecisions.values()]).length === 0;
  if (step === 3) return batch.files.filter(needsReconciliation).every((file) => reconciled.has(file.filename));
  return true;
}
