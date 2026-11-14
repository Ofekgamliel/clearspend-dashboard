import type { PeriodKey, ReportingPeriod } from './common';

export interface RecurringHistoryPoint { month: string; amount: number | null; state: 'charged' | 'missing' | 'not_expected' }
export interface RecurringSeries {
  canonical_group_id: string; display_name: string; category: string; recurring_type: string; cadence: string; cadence_months: number;
  lifecycle_status: string; end_month: string | null; source_aliases: string[]; series_id: string; amount: number | null;
  amount_kind: string; coverage: string; status: string; last_billed_month: string; billed_months: number; typical_amount: number;
  history: RecurringHistoryPoint[];
}
export interface InstallmentCommitment {
  display_name: string; source_alias: string; category: string; progress: string; current_installment: number; total_installments: number;
  charge: number; paid: number; remaining: number; remaining_count: number; status: string; history: RecurringHistoryPoint[];
}
export interface RecurringMetrics {
  recurring_billed: number; recurring_average: number; active_series: number; needs_attention: number; installment_billed: number;
  installment_average: number; installment_plans: number; recurring_share: number; installment_share: number;
}
export interface RecurringVerdictSummary { reviewed: number; recurring: number; not_recurring: number; unresolved: number }
export interface RecurringResponse {
  period: ReportingPeriod; selected_card: string; metrics: RecurringMetrics; series: RecurringSeries[]; commitments: InstallmentCommitment[];
  trend: Array<{ month: string; amount: number }>; verdict_summary: RecurringVerdictSummary;
}
export interface RecurringQuery { period: PeriodKey; month?: string; card: string }
export interface SaveRecurringProfileRequest { canonical_group_id: string; recurring_type: string; cadence: string; lifecycle_status: string; end_month: string }
export interface SaveRecurringProfileResponse {
  canonical_group_id: string; display_name: string; verdict: 'recurring'; recurring_type: string; cadence: string; cadence_months: number;
  lifecycle_status: string; end_month: string | null; updated_at: string;
}
export interface ManageRecurringProfileRequest {
  canonical_group_id: string; verdict: 'recurring' | 'not_recurring'; recurring_type: string; cadence: string; lifecycle_status: string;
  end_month: string; included_aliases: string[];
}
export interface ManageRecurringProfileResponse {
  canonical_group_id: string; display_name: string; verdict: 'recurring' | 'not_recurring'; recurring_type: string | null;
  cadence: string | null; cadence_months: number | null; lifecycle_status: string; end_month: string | null; updated_at: string;
  included_aliases: string[];
}
