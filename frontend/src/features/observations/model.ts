import type { ObservationFinding, ObservationReviewRequest, ObservationsResponse } from '../../api/contracts.ts';
import { formatShortMonth } from '../../shared/format.ts';

export interface ObservationVisual { icon: string; color: string; priority: boolean }
export interface ObservationReviewOption { action: string; resolved: string; resolution: string }
export interface ObservationActivity {
  target: 'transactions' | 'recurring' | 'income';
  label: string;
  transactionIds?: number[];
  search?: string;
  category?: string;
  routine?: boolean;
  recurringSeriesId?: string;
  recurringTab?: 'series' | 'commitments';
}

const visuals: Record<string, ObservationVisual> = {
  'AMOUNT LEFT TREND': { icon: '↘', color: '#c64f64', priority: true },
  'SPENDING ROUTINE SHIFTED': { icon: '≈', color: '#6658e8', priority: true },
  'RECURRING BURDEN SHIFTED': { icon: '↗', color: '#d89a32', priority: false },
  'PERSISTENT INSTALLMENT BURDEN': { icon: '▤', color: '#df793f', priority: false },
  'CATEGORY ROUTINE SHIFTED': { icon: '▥', color: '#278f9d', priority: false },
  'MERCHANT HABIT SHIFTED': { icon: '↕', color: '#329568', priority: false },
  'AMOUNT LEFT DECREASED': { icon: '↘', color: '#c64f64', priority: true },
  'POSSIBLE DUPLICATE': { icon: '≡', color: '#6658e8', priority: true },
  'ADDITIONAL RECURRING CHARGE': { icon: '+', color: '#df793f', priority: false },
  'RECURRING AMOUNT INCREASED': { icon: '↗', color: '#d89a32', priority: false },
  'FEE AMOUNT INCREASED': { icon: '%', color: '#467fc2', priority: false },
  'FIRST FEE OBSERVED': { icon: '◇', color: '#9364c7', priority: false },
  'CATEGORY SPENDING INCREASED': { icon: '▥', color: '#278f9d', priority: false },
  'MERCHANT ACTIVITY CHANGED': { icon: '↕', color: '#329568', priority: false },
  'LARGE AND UNUSUAL PURCHASE': { icon: '‼', color: '#c34f86', priority: true },
  'LARGE PURCHASE': { icon: '↑', color: '#dd6268', priority: false },
  'UNUSUAL TRANSACTION': { icon: '?', color: '#756658', priority: false },
};

const labels: Record<string, [string, string, string]> = {
  'SPENDING ROUTINE SHIFTED': ['Recent monthly average', 'Earlier baseline', 'Lasting change'],
  'AMOUNT LEFT TREND': ['Recent amount left', 'Earlier baseline', 'Lasting change'],
  'CATEGORY ROUTINE SHIFTED': ['Recent monthly average', 'Earlier baseline', 'Lasting change'],
  'RECURRING BURDEN SHIFTED': ['Recent monthly burden', 'Earlier baseline', 'Lasting change'],
  'PERSISTENT INSTALLMENT BURDEN': ['Recent installment burden', 'Duration', 'Plan replacement'],
  'MERCHANT HABIT SHIFTED': ['After change', 'Before change', 'Change and status'],
  'AMOUNT LEFT DECREASED': ['Amount left', 'Recent baseline', 'Change'],
  'CATEGORY SPENDING INCREASED': ['Category spending', 'Three-month median', 'Increase'],
  'POSSIBLE DUPLICATE': ['Charge amount', 'Match basis', 'Candidates'],
  'ADDITIONAL RECURRING CHARGE': ['Charges observed', 'Expected', 'Additional'],
  'RECURRING AMOUNT INCREASED': ['Current amount', 'Baseline / range', 'Increase'],
  'FEE AMOUNT INCREASED': ['Current fee', 'Baseline', 'Increase'],
  'FIRST FEE OBSERVED': ['Fee amount', 'History checked', 'Finding'],
  'MERCHANT ACTIVITY CHANGED': ['This month', 'Recent active-month baseline', 'Activity change'],
  'LARGE AND UNUSUAL PURCHASE': ['Personal amount', 'Comparison', 'Result'],
  'LARGE PURCHASE': ['Personal amount', 'Monthly spending', 'Share of month'],
  'UNUSUAL TRANSACTION': ['Purchase amount', 'Six-month median', 'Difference'],
};

const reviewOptions: Record<string, ObservationReviewOption> = {
  'POSSIBLE DUPLICATE': { action: 'Not duplicate', resolved: 'Marked as not a duplicate', resolution: 'not_duplicate' },
  'ADDITIONAL RECURRING CHARGE': { action: 'Expected charge', resolved: 'Marked as an expected separate charge', resolution: 'expected_charge' },
  'UNUSUAL TRANSACTION': { action: 'Not unusual', resolved: 'Marked as expected / not unusual', resolution: 'not_unusual' },
};

export function observationVisual(type: string): ObservationVisual {
  return visuals[type] ?? { icon: '•', color: '#6658e8', priority: false };
}

export function observationMetricLabels(item: ObservationFinding): [string, string, string] {
  const defaults = labels[item.type] ?? ['Observed value', 'Compared with', 'Result'];
  return [item.valueLabel ?? defaults[0], item.comparisonLabel ?? defaults[1], item.resultLabel ?? defaults[2]];
}

export function observationReviewOption(type: string): ObservationReviewOption | null {
  return reviewOptions[type] ?? null;
}

export function observationReviewRequest(item: ObservationFinding, remove = false): ObservationReviewRequest | null {
  const option = observationReviewOption(item.type);
  if (!option || !item.findingKey) return null;
  return {
    finding_key: item.findingKey,
    observation_type: item.type,
    resolution: option.resolution,
    month: item.month,
    transaction_ids: item.transactionIds ?? [],
    recurring_series_id: item.recurringSeriesId ?? '',
    occurrence_start: item.occurrenceStart ?? '',
    occurrence_end: item.occurrenceEnd ?? '',
    merchant_label: item.label,
    remove,
  };
}

export function observationActivity(item: ObservationFinding): ObservationActivity {
  if (['AMOUNT LEFT DECREASED', 'AMOUNT LEFT TREND', 'SPENDING ROUTINE SHIFTED'].includes(item.type)) {
    return { target: 'income', label: 'View income & spending' };
  }
  if (['CATEGORY SPENDING INCREASED', 'CATEGORY ROUTINE SHIFTED'].includes(item.type)) {
    return { target: 'transactions', label: 'Open category activity', category: item.label, routine: true };
  }
  if (item.type === 'PERSISTENT INSTALLMENT BURDEN') {
    return { target: 'recurring', label: 'Open installment commitments', recurringTab: 'commitments' };
  }
  if (['RECURRING AMOUNT INCREASED', 'FEE AMOUNT INCREASED', 'FIRST FEE OBSERVED', 'RECURRING BURDEN SHIFTED', 'ADDITIONAL RECURRING CHARGE'].includes(item.type)) {
    return { target: 'recurring', label: item.recurringSeriesId ? 'Open recurring series' : 'Open recurring details', recurringSeriesId: item.recurringSeriesId, recurringTab: 'series' };
  }
  if (item.transactionIds?.length) {
    return { target: 'transactions', label: item.transactionIds.length === 1 ? 'Open transaction' : 'Open transactions', transactionIds: item.transactionIds };
  }
  return { target: 'transactions', label: 'Open related activity', search: item.label, routine: ['MERCHANT ACTIVITY CHANGED', 'MERCHANT HABIT SHIFTED'].includes(item.type) };
}

export function observationCount(response: ObservationsResponse): string {
  if (!response.findingCount) return response.historical ? 'NO LASTING SHIFTS' : 'NO ALERTS';
  return `${response.findingCount} ${response.historical ? 'PATTERNS' : 'FINDINGS'} · ${response.typeCount} TYPES`;
}

export function observationScope(response: ObservationsResponse): string {
  const card = response.selectedCard === 'all' ? 'all cards' : 'selected card';
  if (!response.historical) return `${formatShortMonth(response.selectedMonth)} · ${card} · grouped by observation type`;
  const range = `${formatShortMonth(response.observedStart)} – ${formatShortMonth(response.observedEnd)}`;
  return `${range}${response.period === 'all' ? ' · all imported history' : ''} · ${card} · lasting shifts that began during this period`;
}
