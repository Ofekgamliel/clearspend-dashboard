export interface MerchantAlias {
  merchant_normalized: string; merchant_raw: string; category: string; subcategory: string | null; transactions: number; recurring_included: boolean;
}
export interface MerchantRecurringProfile {
  canonical_group_id: string; verdict: 'recurring' | 'not_recurring'; recurring_type: string | null; cadence: string | null;
  cadence_months: number | null; lifecycle_status: string; end_month: string | null; updated_at: string; included_aliases: string[];
}
export interface MerchantRecord {
  canonical_group_id: string; display_name: string; transactions: number; amount: number; last_seen: string; categories: string[];
  aliases: MerchantAlias[]; recurring_profile: MerchantRecurringProfile | null;
}
export interface MerchantReferenceResponse {
  summary: { display_identities: number; mapped_aliases: number; transactions: number; multiple_categories: number; recurring: number };
  categories: string[]; merchants: MerchantRecord[];
}
export interface SaveMerchantAlias { merchant_normalized: string; category: string; subcategory: string }
export interface SaveMerchantRequest { canonical_group_id: string; display_name: string; aliases: SaveMerchantAlias[] }
export interface SaveMerchantResponse {
  status: 'saved'; display_name: string; aliases_updated: number; category_rules_updated: number; transactions_updated: number;
}
