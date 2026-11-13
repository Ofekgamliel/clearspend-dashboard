import { getJson } from './client.ts';
import type { DashboardQuery, DashboardResponse } from './contracts.ts';

export function dashboardUrl(query: DashboardQuery): string {
  const parameters = new URLSearchParams({
    period: query.period,
    month: query.month ?? '',
    card: query.card,
  });
  return `/api/dashboard?${parameters.toString()}`;
}

export function getDashboard(query: DashboardQuery): Promise<DashboardResponse> {
  return getJson<DashboardResponse>(
    dashboardUrl(query),
    'Could not load dashboard filters',
  );
}
