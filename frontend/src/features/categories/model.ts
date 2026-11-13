import type {
  CategoryComparison,
  CategoryComparisonStatus,
  CategoryRow,
} from '../../api/contracts';

export const CATEGORY_COLORS = [
  '#6658e8', '#41b98c', '#e6a14b', '#e76b77', '#5b8def',
  '#a66dd4', '#50a9b8', '#d8834f', '#8f96a8',
] as const;

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

export function buildCategorySegments(
  categories: CategoryRow[],
  colors: readonly string[] = CATEGORY_COLORS,
): CategoryDonutModel {
  const gradientStops: string[] = [];
  let cursor = 0;
  const segments = categories.map((category, index) => {
    const start = Math.min(cursor, 100);
    cursor = Math.min(cursor + category.share, 100);
    const color = colors[index % colors.length] ?? '#8f96a8';
    gradientStops.push(`${color} ${start}% ${cursor}%`);
    return { ...category, color, start, end: cursor };
  });
  if (cursor < 100) gradientStops.push(`#ececf1 ${cursor}% 100%`);
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
