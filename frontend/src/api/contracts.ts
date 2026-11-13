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
  event_id: string | null;
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

export interface TransactionEventRequest {
  transaction_id: number;
  event_id: string;
}

export interface TransactionEventResponse {
  status: 'assigned' | 'unassigned';
  transaction_id: number;
  merchant_raw: string;
  event_id: string | null;
  event_name: string | null;
  event_type: string | null;
  event_destination: string | null;
}

export interface TransactionCategoryRequest {
  transaction_id: number;
  category: string;
  subcategory: string;
}

export interface TransactionCategoryResponse {
  status: 'saved';
  transaction_id: number;
  merchant_raw: string;
  category: string;
  subcategory: string | null;
}

export interface TransactionAdjustmentRequest {
  transaction_id: number;
  remove: boolean;
  reimbursed_amount?: number;
  reimbursement_date?: string;
  note?: string;
}

export interface TransactionAdjustmentResponse {
  status: 'saved' | 'removed';
  transaction_id: number;
  merchant_raw: string;
  adjustment_type?: 'full_reimbursement' | 'partial_reimbursement';
  reimbursed_amount?: number;
  personal_amount: number;
}

export interface MerchantAlias {
  merchant_normalized: string;
  merchant_raw: string;
  category: string;
  subcategory: string | null;
  transactions: number;
  recurring_included: boolean;
}

export interface MerchantRecurringProfile {
  canonical_group_id: string;
  verdict: 'recurring' | 'not_recurring';
  recurring_type: string | null;
  cadence: string | null;
  cadence_months: number | null;
  lifecycle_status: string;
  end_month: string | null;
  updated_at: string;
  included_aliases: string[];
}

export interface MerchantRecord {
  canonical_group_id: string;
  display_name: string;
  transactions: number;
  amount: number;
  last_seen: string;
  categories: string[];
  aliases: MerchantAlias[];
  recurring_profile: MerchantRecurringProfile | null;
}

export interface MerchantReferenceResponse {
  summary: {
    display_identities: number;
    mapped_aliases: number;
    transactions: number;
    multiple_categories: number;
    recurring: number;
  };
  categories: string[];
  merchants: MerchantRecord[];
}

export interface SaveMerchantAlias {
  merchant_normalized: string;
  category: string;
  subcategory: string;
}

export interface SaveMerchantRequest {
  canonical_group_id: string;
  display_name: string;
  aliases: SaveMerchantAlias[];
}

export interface SaveMerchantResponse {
  status: 'saved';
  display_name: string;
  aliases_updated: number;
  category_rules_updated: number;
  transactions_updated: number;
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

export interface SaveRecurringProfileRequest {
  canonical_group_id: string;
  recurring_type: string;
  cadence: string;
  lifecycle_status: string;
  end_month: string;
}

export interface SaveRecurringProfileResponse {
  canonical_group_id: string;
  display_name: string;
  verdict: 'recurring';
  recurring_type: string;
  cadence: string;
  cadence_months: number;
  lifecycle_status: string;
  end_month: string | null;
  updated_at: string;
}

export interface ManageRecurringProfileRequest {
  canonical_group_id: string;
  verdict: 'recurring' | 'not_recurring';
  recurring_type: string;
  cadence: string;
  lifecycle_status: string;
  end_month: string;
  included_aliases: string[];
}

export interface ManageRecurringProfileResponse {
  canonical_group_id: string;
  display_name: string;
  verdict: 'recurring' | 'not_recurring';
  recurring_type: string | null;
  cadence: string | null;
  cadence_months: number | null;
  lifecycle_status: string;
  end_month: string | null;
  updated_at: string;
  included_aliases: string[];
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
  id: string;
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
  id: string;
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

export interface EventMutationRecord {
  id: string;
  name: string;
  event_type: string;
  destination: string | null;
  icon: string | null;
  start_date: string;
  end_date: string;
  status: string;
  budget: number | null;
  notes: string | null;
}

export interface CreateEventRequest {
  name: string;
  event_type: string;
  destination: string;
  start_date: string;
  end_date: string;
  budget: number | null;
  status: 'planned' | 'active' | 'completed';
}

export interface CreateEventResponse {
  status: 'created';
  event: EventMutationRecord;
}

export interface SaveEventRequest extends Omit<CreateEventRequest, 'status'> {
  event_id: string;
  status: 'planned' | 'active' | 'completed' | 'cancelled';
}

export interface SaveEventResponse {
  status: 'updated';
  event: EventMutationRecord;
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

export interface ObservationFinding {
  type: string;
  month: string;
  label: string;
  title: string;
  description: string;
  score: number;
  value: string;
  comparison?: string;
  result?: string;
  evidence: string[];
  entityLabel?: string;
  entitySublabel?: string;
  comparisonDetail?: string;
  comparisonLabel?: string;
  valueLabel?: string;
  resultLabel?: string;
  ruleText?: string;
  eventLabel?: string;
  patternPeriod?: string;
  habitKind?: string;
  findingKey?: string;
  transactionIds?: number[];
  recurringSeriesId?: string;
  occurrenceStart?: string;
  occurrenceEnd?: string;
  cardSummary?: string;
  cardComparison?: { primary: string; secondary: string };
}

export interface ObservationGroup extends ObservationFinding {
  items: ObservationFinding[];
  merchantPreview?: string;
  compactCategories?: Array<{ label: string; result: string }>;
  singular?: string;
  entities?: string;
  primaryLabel?: string;
}

export interface ObservationsResponse {
  period: PeriodKey;
  selectedCard: string;
  selectedMonth: string;
  observedStart: string;
  observedEnd: string;
  historical: boolean;
  findingCount: number;
  typeCount: number;
  findings: ObservationFinding[];
  groups: ObservationGroup[];
}

export interface ObservationsQuery {
  period: PeriodKey;
  month?: string;
  card: string;
  incomeHidden: boolean;
}

export interface ObservationReviewRequest {
  finding_key: string;
  observation_type: string;
  resolution: string;
  month: string;
  transaction_ids: number[];
  recurring_series_id: string;
  occurrence_start: string;
  occurrence_end: string;
  merchant_label: string;
  remove: boolean;
}

export interface ObservationReviewResponse {
  status: 'reviewed' | 'restored';
  finding_key: string;
  resolution?: string;
  changed?: boolean;
}
