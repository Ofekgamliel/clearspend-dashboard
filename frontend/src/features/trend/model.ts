import type { CategoryRow, ReportingPeriod, TrendPoint } from '../../api/contracts';
import { CATEGORY_COLORS } from '../categories/model.ts';

export const CHART = { width: 720, height: 204, top: 14, bottom: 218 } as const;

export interface TrendLabel { x: number; label: string }
export interface TrendSegment { category: string; amount: number; color: string; x: number; y: number; width: number; height: number }
export interface DailyTrendPoint extends TrendPoint {
  cumulative: number;
  cumulativeDisplay: number;
  gross: number;
  refunds: number;
  x: number;
  lineY: number;
  segments: TrendSegment[];
}

export interface MonthlyTrendModel {
  days: DailyTrendPoint[];
  dailyMax: number;
  cumulativeMax: number;
  path: string;
  labels: TrendLabel[];
}

export interface BillingBar { bucket: string; amount: number; income: number; spendingX: number; spendingY: number; spendingHeight: number; incomeX: number; incomeY: number; incomeHeight: number; width: number; hitX: number; hitWidth: number }
export interface BillingTrendModel { bars: BillingBar[]; max: number; labels: TrendLabel[]; showIncome: boolean }

function parseDate(value: string): Date {
  return new Date(`${value}T12:00:00Z`);
}

function dateKey(value: Date): string {
  return `${value.getUTCFullYear()}-${String(value.getUTCMonth() + 1).padStart(2, '0')}-${String(value.getUTCDate()).padStart(2, '0')}`;
}

export function buildMonthlyTrend(
  points: TrendPoint[],
  categories: CategoryRow[],
  period: ReportingPeriod,
  today = new Date(),
): MonthlyTrendModel {
  if (!period.start || !period.end) return { days: [], dailyMax: 1, cumulativeMax: 1, path: '', labels: [] };
  const activity = new Map(points.map((point) => [point.bucket, point]));
  const categoryNames = categories.map((item) => item.category);
  points.forEach((point) => (point.categories ?? []).forEach((item) => {
    if (!categoryNames.includes(item.category)) categoryNames.push(item.category);
  }));
  const colors = new Map(categoryNames.map((category, index) => [category, CATEGORY_COLORS[index % CATEGORY_COLORS.length] ?? '#6658e8']));
  const positions = new Map(categoryNames.map((category, index) => [category, index]));
  const start = parseDate(period.start);
  const periodEnd = parseDate(period.end);
  const todayUtc = new Date(Date.UTC(today.getFullYear(), today.getMonth(), today.getDate(), 12));
  const currentMonth = start.getUTCFullYear() === todayUtc.getUTCFullYear() && start.getUTCMonth() === todayUtc.getUTCMonth();
  const end = currentMonth && todayUtc < periodEnd ? todayUtc : periodEnd;
  const rawDays: Array<TrendPoint & { cumulative: number; cumulativeDisplay: number; gross: number; refunds: number }> = [];
  let cumulative = 0;
  for (let cursor = new Date(start); cursor <= end; cursor.setUTCDate(cursor.getUTCDate() + 1)) {
    const bucket = dateKey(cursor);
    const point = activity.get(bucket);
    const amount = Number(point?.amount) || 0;
    const dayCategories = point?.categories ?? [];
    cumulative += amount;
    rawDays.push({
      bucket,
      amount,
      categories: dayCategories,
      cumulative,
      cumulativeDisplay: Math.max(cumulative, 0),
      gross: dayCategories.reduce((sum, item) => sum + Math.max(Number(item.amount) || 0, 0), 0),
      refunds: Math.abs(dayCategories.reduce((sum, item) => sum + Math.min(Number(item.amount) || 0, 0), 0)),
    });
  }
  const dailyMax = Math.max(...rawDays.map((point) => point.gross), 1);
  const cumulativeMax = Math.max(...rawDays.map((point) => point.cumulativeDisplay), 1);
  const slot = CHART.width / Math.max(rawDays.length, 1);
  const barWidth = Math.max(Math.min(slot * .58, 15), 3);
  const days: DailyTrendPoint[] = rawDays.map((point, index) => {
    const x = index * slot + (slot - barWidth) / 2;
    let cursor = CHART.bottom;
    const segments = [...(point.categories ?? [])]
      .filter((item) => Number(item.amount) > 0)
      .sort((left, right) => (positions.get(left.category) ?? 999) - (positions.get(right.category) ?? 999))
      .map((item) => {
        const height = Number(item.amount) / dailyMax * CHART.height;
        cursor -= height;
        return { category: item.category, amount: item.amount, color: colors.get(item.category) ?? '#6658e8', x, y: cursor, width: barWidth, height: Math.max(height, .8) };
      });
    return { ...point, x: index * slot + slot / 2, lineY: CHART.bottom - point.cumulativeDisplay / cumulativeMax * CHART.height, segments };
  });
  const path = days.map((point, index) => `${index ? 'L' : 'M'}${point.x.toFixed(1)} ${point.lineY.toFixed(1)}`).join(' ');
  const step = Math.ceil(days.length / 7);
  const labels = days.flatMap((point, index) => (index === 0 || index === days.length - 1 || index % step === 0)
    ? [{ x: point.x / CHART.width * 100, label: String(Number(point.bucket.slice(-2))) }]
    : []);
  return { days, dailyMax, cumulativeMax, path, labels };
}

export function buildBillingTrend(points: TrendPoint[], showIncome: boolean): BillingTrendModel {
  const values = points.flatMap((point) => showIncome
    ? [Math.max(Number(point.amount) || 0, 0), Math.max(Number(point.income) || 0, 0)]
    : [Math.max(Number(point.amount) || 0, 0)]);
  const max = Math.max(...values, 1);
  const slot = CHART.width / Math.max(points.length, 1);
  const groupWidth = Math.min(slot * .68, 38);
  const gap = 3;
  const width = showIncome ? (groupWidth - gap) / 2 : Math.min(groupWidth, 24);
  const bars = points.map((point, index) => {
    const center = index * slot + slot / 2;
    const amount = Math.max(Number(point.amount) || 0, 0);
    const income = Math.max(Number(point.income) || 0, 0);
    const spendingHeight = amount / max * CHART.height;
    const incomeHeight = income / max * CHART.height;
    return {
      bucket: point.bucket, amount, income,
      spendingX: showIncome ? center + gap / 2 : center - width / 2,
      spendingY: CHART.bottom - spendingHeight, spendingHeight,
      incomeX: center - groupWidth / 2, incomeY: CHART.bottom - incomeHeight, incomeHeight,
      width, hitX: index * slot, hitWidth: slot,
    };
  });
  const step = Math.ceil(points.length / 8);
  const labels = points.flatMap((point, index) => (index === 0 || index === points.length - 1 || index % step === 0)
    ? [{ x: (index + .5) / points.length * 100, label: point.bucket }]
    : []);
  return { bars, max, labels, showIncome };
}

export function axisValues(max: number): number[] {
  return [max, max * .75, max * .5, max * .25, 0];
}
