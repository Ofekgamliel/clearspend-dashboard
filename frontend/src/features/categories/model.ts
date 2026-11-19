import type {
  CategoryComparison,
  CategoryComparisonStatus,
  CategoryRow,
} from '../../api/contracts';
import { CATEGORY_COLORS, CHART_EMPTY_COLOR } from '../../shared/visualization/chartPalette.ts';

export interface CategorySegment extends CategoryRow {
  color: string;
  start: number;
  end: number;
}

export interface CategoryDonutModel {
  ariaLabel: string;
  gradient: string;
  segments: CategorySegment[];
}

export interface CategoryComparisonModel {
  label: string;
  previousMonth: string;
  status: CategoryComparisonStatus;
}

export function categorySegmentAtPoint(
  x: number,
  y: number,
  size: number,
  segments: CategorySegment[],
): CategorySegment | null {
  if (!size || !segments.length) return null;
  const radius = size / 2;
  const offsetX = x - radius;
  const offsetY = y - radius;
  const distance = Math.hypot(offsetX, offsetY);
  if (distance < size * 0.32 || distance > radius) return null;
  const angle = (Math.atan2(offsetY, offsetX) * 180 / Math.PI + 450) % 360;
  const percentage = angle / 3.6;
  return segments.find((segment) => percentage >= segment.start && percentage < segment.end) ?? null;
}

export function buildCategorySegments(
  categories: CategoryRow[],
  colors: readonly string[] = CATEGORY_COLORS,
): CategoryDonutModel {
  const gradientStops: string[] = [];
  let cursor = 0;
  const segments = categories.map((category, index) => {
    const start = Math.min(cursor, 100);
    cursor = Math.min(cursor + category.share, 100);
    const color = colors[index % colors.length] ?? 'var(--ui-chart-9)';
    gradientStops.push(`${color} ${start}% ${cursor}%`);
    return { ...category, color, start, end: cursor };
  });
  if (cursor < 100) gradientStops.push(`${CHART_EMPTY_COLOR} ${cursor}% 100%`);
  return {
    ariaLabel: categories
      .map((category) => `${category.category}: ${category.share}%`)
      .join(', '),
    gradient: `conic-gradient(${gradientStops.join(',')})`,
    segments,
  };
}

export function categoryComparisonModel(
  category: CategoryRow,
  comparison: CategoryComparison,
): CategoryComparisonModel | null {
  if (!comparison.previous_month) return null;
  const status = category.comparison ?? 'unavailable';
  const change = Math.abs(Number(category.change_percent));
  const labels: Record<CategoryComparisonStatus, string> = {
    up: `↑ ${change}%`,
    down: `↓ ${change}%`,
    same: '0%',
    new: 'New',
    unavailable: '—',
  };
  return {
    label: labels[status],
    previousMonth: comparison.previous_month,
    status,
  };
}
