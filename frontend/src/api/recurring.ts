import { getJson, postJson } from './client.ts';
import type {
  RecurringQuery,
  RecurringResponse,
  RecurringUpcomingQuery,
  RecurringUpcomingResponse,
  SaveRecurringProfileRequest,
  SaveRecurringProfileResponse,
} from './contracts.ts';

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

export function recurringUpcomingUrl(query: RecurringUpcomingQuery): string {
  const parameters = new URLSearchParams({ view: 'upcoming', card: query.card });
  return `/api/recurring?${parameters.toString()}`;
}

export function getRecurringUpcoming(
  query: RecurringUpcomingQuery,
): Promise<RecurringUpcomingResponse> {
  return getJson<RecurringUpcomingResponse>(
    recurringUpcomingUrl(query),
    'Could not load upcoming recurring payments',
  );
}

export function saveRecurringProfile(
  request: SaveRecurringProfileRequest,
): Promise<SaveRecurringProfileResponse> {
  return postJson<SaveRecurringProfileResponse, SaveRecurringProfileRequest>(
    '/api/recurring-profile',
    request,
    'Could not update recurring profile',
  );
}
