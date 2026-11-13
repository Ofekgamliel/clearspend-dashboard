import type { DashboardCard } from '../../api/contracts';

const MONTH_PATTERN = /^\d{4}-(0[1-9]|1[0-2])$/;

export function normalizeAvailableMonths(months: string[]): string[] {
  return [...new Set(months.filter((month) => MONTH_PATTERN.test(month)))].sort().reverse();
}

export function selectedMonth(
  requested: string,
  periodStart: string | null,
  availableMonths: string[],
): string {
  const normalized = normalizeAvailableMonths(availableMonths);
  if (normalized.includes(requested)) return requested;
  const resolved = periodStart?.slice(0, 7) ?? '';
  if (normalized.includes(resolved)) return resolved;
  return normalized[0] ?? '';
}

export function cardLabel(card: DashboardCard | undefined): string {
  return card ? `${card.product_name} •• ${card.card_last4}` : 'All cards';
}
