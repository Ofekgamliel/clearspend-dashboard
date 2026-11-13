export type PeriodKey = 'month' | 'year' | 'all';
export type EventScope = 'all' | 'routine';
export type CategoryComparisonStatus = 'up' | 'down' | 'same' | 'new' | 'unavailable';

export interface ReportingPeriod {
  key: PeriodKey;
  start: string | null;
  end: string | null;
  label: string;
}

export interface CategoryRow {
  category: string;
  amount: number;
  transactions: number;
  merchants: number;
  share: number;
  previous_amount?: number;
  comparison?: CategoryComparisonStatus;
  change_percent?: number | null;
}

export interface CategoryComparison {
  available: boolean;
  previous_month: string | null;
}

export interface CategoriesResponse {
  period: ReportingPeriod;
  selected_card: string;
  event_scope: EventScope;
  total: number;
  categories: CategoryRow[];
  category_comparison: CategoryComparison;
}

export interface CategoriesQuery {
  period: PeriodKey;
  month?: string;
  card: string;
  eventScope: EventScope;
}

export interface DashboardCard {
  key: string;
  provider: string;
  product_name: string;
  card_last4: string;
  amount: number;
  share: number;
  transactions: number;
}

export interface DashboardFiltersResponse {
  period: ReportingPeriod;
  selected_card: string;
  cards: DashboardCard[];
  available_months: string[];
}

export interface IncomeAverages {
  spending: number;
  amount_left: number;
  spending_months: number;
  amount_left_months: number;
  start_month: string | null;
  end_month: string | null;
  current_month_partial: boolean;
}

export interface IncomeSummary {
  has_income: boolean;
  income: number;
  spending: number;
  charges: number;
  refunds: number;
  remaining: number;
  remaining_percentage: number | null;
  spent_percentage: number | null;
  scope: 'all_cards';
  averages: IncomeAverages;
}

export interface DashboardResponse extends DashboardFiltersResponse {
  metrics: DashboardMetrics;
  income_summary: IncomeSummary;
  categories: CategoryRow[];
  category_comparison: CategoryComparison;
  trend: TrendPoint[];
  trend_mode: 'purchase_activity' | 'billing_summary';
  purchase_activity_summary: PurchaseActivitySummary | null;
  recent_transactions: RecentTransaction[];
}

export interface RecentTransaction {
  merchant_raw: string;
  category: string;
  subcategory: string | null;
  provider: string;
  card_last4: string;
  transaction_date: string | null;
  billing_date: string | null;
  billing_month: string | null;
  billing_month_source: string | null;
  amount: number;
  personal_amount: number;
  charged_currency: string;
  adjustment_type: string | null;
  reimbursed_amount: number | null;
  reimbursement_date: string | null;
}

export interface TransactionRow extends RecentTransaction {
  id: number;
  merchant_normalized: string;
  canonical_merchant_id: string;
  merchant_display_name: string;
  merchant_category: string;
  category_source: string;
  source_sheet: string | null;
  installment_number: number | null;
  installment_total: number | null;
  reimbursement_note: string | null;
  original_amount: number | null;
  original_currency: string | null;
  transaction_type: string | null;
  voucher_number: string | null;
  notes: string | null;
  execution_method: string | null;
  exchange_rate: number | null;
  event_id: number | null;
  event_name: string | null;
  event_type: string | null;
  event_destination: string | null;
}

export interface TransactionsResponse {
  period: ReportingPeriod;
  selected_card: string;
  event_scope: EventScope;
  total: number;
  transactions: TransactionRow[];
}

export interface TransactionsQuery {
  period: PeriodKey;
  month?: string;
  card: string;
  search?: string;
  category?: string;
  eventScope?: EventScope;
}

export interface RecurringHistoryPoint {
  month: string;
  amount: number | null;
  state: 'charged' | 'missing' | 'not_expected';
}

export interface RecurringSeries {
  canonical_group_id: string;
  display_name: string;
  category: string;
  recurring_type: string;
  cadence: string;
  cadence_months: number;
  lifecycle_status: string;
  end_month: string | null;
  source_aliases: string[];
  series_id: string;
  amount: number | null;
  amount_kind: string;
  coverage: string;
  status: string;
  last_billed_month: string;
  billed_months: number;
  typical_amount: number;
  history: RecurringHistoryPoint[];
}

export interface InstallmentCommitment {
  display_name: string;
  source_alias: string;
  category: string;
  progress: string;
  current_installment: number;
  total_installments: number;
  charge: number;
  paid: number;
  remaining: number;
  remaining_count: number;
  status: string;
  history: RecurringHistoryPoint[];
}

export interface RecurringMetrics {
  recurring_billed: number;
  recurring_average: number;
  active_series: number;
  needs_attention: number;
  installment_billed: number;
  installment_average: number;
  installment_plans: number;
  recurring_share: number;
  installment_share: number;
}

export interface RecurringVerdictSummary {
  reviewed: number;
  recurring: number;
  not_recurring: number;
  unresolved: number;
}

export interface RecurringResponse {
  period: ReportingPeriod;
  selected_card: string;
  metrics: RecurringMetrics;
  series: RecurringSeries[];
  commitments: InstallmentCommitment[];
  trend: Array<{ month: string; amount: number }>;
  verdict_summary: RecurringVerdictSummary;
}

export interface RecurringQuery {
  period: PeriodKey;
  month?: string;
  card: string;
}

export interface EventTransaction {
  id: number;
  merchant_raw: string;
  merchant_display_name: string;
  category: string;
  transaction_date: string;
  provider: string;
  card_last4: string;
  amount: number;
  personal_amount: number;
}

export interface EventSummary {
  id: number;
  name: string;
  event_type: string;
  destination: string | null;
  icon: string | null;
  start_date: string;
  end_date: string;
  status: string;
  budget: number | null;
  notes: string | null;
  transactions: EventTransaction[];
  transaction_count: number;
  amount: number;
  total_transaction_count: number;
  total_amount: number;
  category_count: number;
  card_count: number;
}

export interface AvailableEvent {
  id: number;
  name: string;
  event_type: string;
  destination: string | null;
  icon: string | null;
  start_date: string;
  end_date: string;
  status: string;
}

export interface EventsResponse {
  period: ReportingPeriod;
  selected_card: string;
  events: EventSummary[];
  available_events: AvailableEvent[];
}

export interface EventsQuery {
  period: PeriodKey;
  month?: string;
  card: string;
}

export interface DashboardMetrics {
  spent: number;
  refunds: number;
  transactions: number;
  daily_average: number;
  active_days: number;
}

export interface TrendCategoryAmount {
  category: string;
  amount: number;
}

export interface TrendPoint {
  bucket: string;
  amount: number;
  income?: number;
  categories?: TrendCategoryAmount[];
}

export interface PurchaseActivitySummary {
  total: number;
  purchases: number;
  active_days: number;
  installment_plans: number;
  billed_charges: number;
  billed_refunds: number;
}

export interface DashboardQuery {
  period: PeriodKey;
  month?: string;
  card: string;
}
