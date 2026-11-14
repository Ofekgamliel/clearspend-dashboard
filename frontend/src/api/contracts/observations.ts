import type { PeriodKey } from './common';

export interface ObservationFinding {
  type: string; month: string; label: string; title: string; description: string; score: number; value: string;
  comparison?: string; result?: string; evidence: string[]; entityLabel?: string; entitySublabel?: string; comparisonDetail?: string;
  comparisonLabel?: string; valueLabel?: string; resultLabel?: string; ruleText?: string; eventLabel?: string; patternPeriod?: string;
  habitKind?: string; findingKey?: string; transactionIds?: number[]; recurringSeriesId?: string; occurrenceStart?: string;
  occurrenceEnd?: string; cardSummary?: string; cardComparison?: { primary: string; secondary: string };
}
export interface ObservationGroup extends ObservationFinding {
  items: ObservationFinding[]; merchantPreview?: string; compactCategories?: Array<{ label: string; result: string }>;
  singular?: string; entities?: string; primaryLabel?: string;
}
export interface ObservationsResponse {
  period: PeriodKey; selectedCard: string; selectedMonth: string; observedStart: string; observedEnd: string; historical: boolean;
  findingCount: number; typeCount: number; findings: ObservationFinding[]; groups: ObservationGroup[];
}
export interface ObservationsQuery { period: PeriodKey; month?: string; card: string; incomeHidden: boolean }
export interface ObservationReviewRequest {
  finding_key: string; observation_type: string; resolution: string; month: string; transaction_ids: number[]; recurring_series_id: string;
  occurrence_start: string; occurrence_end: string; merchant_label: string; remove: boolean;
}
export interface ObservationReviewResponse { status: 'reviewed' | 'restored'; finding_key: string; resolution?: string; changed?: boolean }
