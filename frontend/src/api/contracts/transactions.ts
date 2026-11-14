import type { EventScope, PeriodKey, ReportingPeriod } from './common';

export interface RecentTransaction {
  merchant_raw: string; category: string; subcategory: string | null; provider: string; card_last4: string;
  transaction_date: string | null; billing_date: string | null; billing_month: string | null; billing_month_source: string | null;
  amount: number; personal_amount: number; charged_currency: string; adjustment_type: string | null;
  reimbursed_amount: number | null; reimbursement_date: string | null;
}

export interface TransactionRow extends RecentTransaction {
  id: number; merchant_normalized: string; canonical_merchant_id: string; merchant_display_name: string; merchant_category: string;
  category_source: string; source_sheet: string | null; installment_number: number | null; installment_total: number | null;
  reimbursement_note: string | null; original_amount: number | null; original_currency: string | null; transaction_type: string | null;
  voucher_number: string | null; notes: string | null; execution_method: string | null; exchange_rate: number | null;
  event_id: string | null; event_name: string | null; event_type: string | null; event_destination: string | null;
}

export interface TransactionsResponse { period: ReportingPeriod; selected_card: string; event_scope: EventScope; total: number; transactions: TransactionRow[] }
export interface TransactionsQuery { period: PeriodKey; month?: string; card: string; search?: string; category?: string; eventScope?: EventScope }
export interface TransactionEventRequest { transaction_id: number; event_id: string }
export interface TransactionEventResponse {
  status: 'assigned' | 'unassigned'; transaction_id: number; merchant_raw: string; event_id: string | null; event_name: string | null;
  event_type: string | null; event_destination: string | null;
}
export interface TransactionCategoryRequest { transaction_id: number; category: string; subcategory: string }
export interface TransactionCategoryResponse { status: 'saved'; transaction_id: number; merchant_raw: string; category: string; subcategory: string | null }
export interface TransactionAdjustmentRequest {
  transaction_id: number; remove: boolean; reimbursed_amount?: number; reimbursement_date?: string; note?: string;
}
export interface TransactionAdjustmentResponse {
  status: 'saved' | 'removed'; transaction_id: number; merchant_raw: string;
  adjustment_type?: 'full_reimbursement' | 'partial_reimbursement'; reimbursed_amount?: number; personal_amount: number;
}
