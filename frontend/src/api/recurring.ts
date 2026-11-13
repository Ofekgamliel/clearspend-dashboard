import { getJson } from './client.ts';
import type { RecurringQuery, RecurringResponse } from './contracts.ts';

export function recurringUrl(query: RecurringQuery): string {
  const parameters = new URLSearchParams({
    period: query.period,
    month: query.month ?? '',
    card: query.card,
  });
  return `/api/recurring?${parameters.toString()}`;
}

export function getRecurring(query: RecurringQuery): Promise<RecurringResponse> {
  return getJson<RecurringResponse>(recurringUrl(query), 'Could not load recurring spending');
}
