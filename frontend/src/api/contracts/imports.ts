export interface StagedReconciliation { status: string; parsed_total: number | null; official_total: number | null; difference: number | null }
export interface StagedCoverage { card_last4: string; purchase_date_from: string | null; purchase_date_to: string | null; statement_as_of_date: string | null }
export interface StagedFile {
  filename: string; kind: string; status: string; format: string; provider: string | null; product_name?: string | null;
  card_last4?: string | null; statement_range?: string | null; parsed?: number; new_rows?: number; exact_duplicates?: number;
  possible_duplicates?: number; pending_rows?: number; installment_plans?: number; coverage?: StagedCoverage[]; reconciliation?: StagedReconciliation;
}
export interface StagedTransaction {
  candidate_id?: string; transaction_key?: string; file_index?: number; filename: string; merchant: string; merchant_normalized: string;
  transaction_date: string | null; billing_date?: string | null; billing_month?: string | null; amount: number | null; currency?: string | null;
  original_amount?: number | null; original_currency?: string | null; card_last4?: string | null; source_status?: string;
  installment_number?: number | null; installment_total?: number | null; reason?: string; matched_transaction_id?: number;
  matched_transaction_ids?: number[]; matched_rows?: Array<{ id: number; merchant_raw?: string; provider?: string; card_last4?: string; transaction_date?: string | null; billing_date?: string | null; billing_month?: string | null }>; reviewed_new?: boolean;
}
export interface StagedMerchant {
  merchant_normalized: string; merchant_raw: string; display_name: string; canonical_group_id: string | null; category: string;
  subcategory: string | null; provider_category: string | null; needs_review: boolean; match_source: string; transactions: number; amount: number;
  providers: string[]; first_date: string; last_date: string;
}
export interface DisplayIdentityReference {
  canonical_group_id: string; display_name: string; aliases: number; transactions: number; alias_names: string[];
  category_status: 'unanimous' | 'mixed' | 'unmapped'; category: string | null; categories: Array<{ category: string; aliases: number }>;
}
export interface StagedImportBatch {
  batch_id: string; files: StagedFile[]; merchants: StagedMerchant[]; categories: string[]; display_identities: DisplayIdentityReference[];
  exact_duplicates: StagedTransaction[]; possible_duplicates: StagedTransaction[]; new_transactions: StagedTransaction[];
  pending_transactions: StagedTransaction[]; coverage_warnings: Array<{ card_last4: string; filename: string; message: string; imports?: string[] }>;
  upload_errors: Array<{ filename: string; status: string; error?: string }>;
}
export interface ImportMerchantDecision {
  merchant_normalized: string; resolution: 'create' | 'link' | 'provider' | 'needs_review' | 'exclude'; category: string;
  display_name: string; canonical_group_id: string; scope: 'exact' | 'batch'; suggested_match?: boolean;
}
export interface CommitImportRequest {
  batch_id: string; decisions: ImportMerchantDecision[]; duplicate_decisions: Array<{ candidate_id: string; action: 'skip' | 'import' }>;
  reconciled_files: string[];
}
export interface CommitImportResponse { status: 'committed'; backup: string; results: Array<{ inserted?: number; duplicates?: number; filename: string; status: string }> }
export interface CancelImportResponse { status: 'discarded'; removed: boolean }
export interface ImportAuditRecord { id:number; original_name:string; provider:string; card_last4:string|null; statement_range:string|null; status:string; parsed_rows:number; inserted_rows:number; duplicate_rows:number; imported_at:string; coverage:Array<StagedCoverage & { pending_rows:number; outside_cycle_rows:number; statement_month?:string|null }> }
export interface MappingReferenceResponse { summary:{ merchants:number; needs_review:number; categorized:number }; review_merchants:Array<{merchant_raw:string;merchant_normalized:string;transactions:number;amount:number}>; recent_imports:ImportAuditRecord[]; mappings:Array<{merchant_normalized:string;category:string;subcategory:string|null;updated_at:string}>; category_suggestions:string[] }
