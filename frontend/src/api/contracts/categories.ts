import type { EventScope, PeriodKey, ReportingPeriod } from './common';

export type CategoryComparisonStatus = 'up' | 'down' | 'same' | 'new' | 'unavailable';

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
