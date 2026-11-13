import type { MerchantRecord, SaveMerchantRequest } from '../../api/contracts.ts';

export type MerchantReviewFilter = 'all' | 'needs_review' | 'mixed_categories';

export interface MerchantAliasDraft {
  merchant_normalized: string;
  merchant_raw: string;
  transactions: number;
  originalCategory: string;
  originalSubcategory: string;
  category: string;
  subcategory: string;
}

export interface MerchantDraft {
  canonicalGroupId: string;
  originalDisplayName: string;
  displayName: string;
  transactions: number;
  aliases: MerchantAliasDraft[];
}

const collator = new Intl.Collator(['he', 'en'], { numeric: true, sensitivity: 'base' });

export function merchantNeedsReview(merchant: MerchantRecord): boolean {
  return merchant.aliases.some((alias) => alias.category === 'Needs review');
}

export function filterMerchants(merchants: MerchantRecord[], search: string, filter: MerchantReviewFilter): MerchantRecord[] {
  const needle = search.trim().toLocaleLowerCase();
  return merchants.filter((merchant) => {
    if (filter === 'needs_review' && !merchantNeedsReview(merchant)) return false;
    if (filter === 'mixed_categories' && merchant.categories.length < 2) return false;
    if (!needle) return true;
    return [merchant.display_name, merchant.canonical_group_id, ...merchant.aliases.flatMap((alias) => [alias.merchant_raw, alias.merchant_normalized])]
      .some((value) => value.toLocaleLowerCase().includes(needle));
  }).sort((left, right) => collator.compare(left.display_name, right.display_name));
}

export function createMerchantDraft(merchant: MerchantRecord): MerchantDraft {
  return {
    canonicalGroupId: merchant.canonical_group_id,
    originalDisplayName: merchant.display_name,
    displayName: merchant.display_name,
    transactions: merchant.transactions,
    aliases: merchant.aliases.map((alias) => ({
      merchant_normalized: alias.merchant_normalized,
      merchant_raw: alias.merchant_raw,
      transactions: alias.transactions,
      originalCategory: alias.category,
      originalSubcategory: alias.subcategory ?? '',
      category: alias.category,
      subcategory: alias.subcategory ?? '',
    })),
  };
}

export function changedAliases(draft: MerchantDraft): MerchantAliasDraft[] {
  return draft.aliases.filter((alias) => alias.category !== alias.originalCategory || alias.subcategory !== alias.originalSubcategory);
}

export function merchantDraftChanged(draft: MerchantDraft): boolean {
  return draft.displayName.trim() !== draft.originalDisplayName || changedAliases(draft).length > 0;
}

export function merchantDraftError(draft: MerchantDraft): string {
  if (!draft.displayName.trim()) return 'Display name is required.';
  if (draft.aliases.some((alias) => !alias.category.trim())) return 'Every edited alias needs a category.';
  if (!merchantDraftChanged(draft)) return 'No merchant changes to review.';
  return '';
}

export function merchantImpact(draft: MerchantDraft): string[] {
  const aliases = changedAliases(draft);
  const items: string[] = [];
  if (draft.displayName.trim() !== draft.originalDisplayName) {
    items.push(`Rename ${draft.aliases.length} exact aliases across ${draft.transactions} existing transactions.`);
  }
  if (aliases.length) {
    const transactions = aliases.reduce((total, alias) => total + alias.transactions, 0);
    items.push(`Update permanent categories for ${aliases.length} exact aliases and ${transactions} existing transactions.`);
    items.push('Future imports with those exact normalized names will use the reviewed categories.');
  }
  if (new Set(draft.aliases.map((alias) => alias.category)).size > 1) {
    items.push('This display identity intentionally contains aliases with different categories.');
  }
  return items;
}

export function merchantSaveRequest(draft: MerchantDraft): SaveMerchantRequest {
  return {
    canonical_group_id: draft.canonicalGroupId,
    display_name: draft.displayName.trim(),
    aliases: changedAliases(draft).map((alias) => ({
      merchant_normalized: alias.merchant_normalized,
      category: alias.category.trim(),
      subcategory: alias.subcategory.trim(),
    })),
  };
}
