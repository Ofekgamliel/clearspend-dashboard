import type { IncomeSummary, ReportingPeriod } from '../../api/contracts';
import { formatShortMonth } from '../../shared/format.ts';

export interface IncomeAllocation {
  spentWidth: number;
  leftWidth: number;
  spentLabel: string;
  leftLabel: string;
  over: boolean;
  unavailable: boolean;
}

export function incomeAllocation(summary: IncomeSummary): IncomeAllocation {
  const spent = Number(summary.spent_percentage ?? 0);
  const left = Number(summary.remaining_percentage ?? 0);
  const boundedSpent = summary.has_income ? Math.min(Math.max(spent, 0), 100) : 100;
  return {
    spentWidth: boundedSpent,
    leftWidth: summary.has_income ? 100 - boundedSpent : 100,
    spentLabel: summary.has_income ? `${spent}% spent` : 'Income unavailable',
    leftLabel: summary.has_income && left > 0 ? `${left}% left` : '',
    over: summary.has_income && spent > 100,
    unavailable: !summary.has_income,
  };
}

export function incomePeriodLabel(period: ReportingPeriod, summary: IncomeSummary): string {
  const partial = period.key === 'month' && summary.averages.current_month_partial;
  return `${period.label} · All cards${partial ? ' · Partial month' : ''}`;
}

export function averageRangeLabel(summary: IncomeSummary): string {
  const averages = summary.averages;
  const range = averages.start_month && averages.end_month
    ? `${formatShortMonth(averages.start_month)} – ${formatShortMonth(averages.end_month)}`
    : 'No monthly history';
  return `${range}${averages.current_month_partial ? ' · Includes partial current month' : ''}`;
}
