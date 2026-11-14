import type { CategoryComparison, CategoryRow } from './categories';
import type { PeriodKey, ReportingPeriod } from './common';
import type { RecentTransaction } from './transactions';

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

export interface DashboardMetrics {
  spent: number;
  refunds: number;
  transactions: number;
  daily_average: number;
  active_days: number;
}

export interface TrendCategoryAmount { category: string; amount: number }
export interface TrendPoint { bucket: string; amount: number; income?: number; categories?: TrendCategoryAmount[] }
export interface PurchaseActivitySummary {
  total: number; purchases: number; active_days: number; installment_plans: number; billed_charges: number; billed_refunds: number;
}
export interface DashboardLatestImport { original_name: string; imported_at: string; status: string }

export interface DashboardResponse extends DashboardFiltersResponse {
  metrics: DashboardMetrics;
  income_summary: IncomeSummary;
  categories: CategoryRow[];
  category_comparison: CategoryComparison;
  trend: TrendPoint[];
  trend_mode: 'purchase_activity' | 'billing_summary';
  purchase_activity_summary: PurchaseActivitySummary | null;
  recent_transactions: RecentTransaction[];
  latest_import: DashboardLatestImport | null;
}

export interface DashboardQuery { period: PeriodKey; month?: string; card: string }
