export type PeriodKey = 'month' | 'year' | 'all';
export type EventScope = 'all' | 'routine';

export interface ReportingPeriod {
  key: PeriodKey;
  start: string | null;
  end: string | null;
  label: string;
}
