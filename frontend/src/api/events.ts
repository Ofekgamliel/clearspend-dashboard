import { getJson } from './client.ts';
import type { EventsQuery, EventsResponse } from './contracts.ts';

export function eventsUrl(query: EventsQuery): string {
  const parameters = new URLSearchParams({
    period: query.period,
    month: query.month ?? '',
    card: query.card,
  });
  return `/api/events?${parameters.toString()}`;
}

export function getEvents(query: EventsQuery): Promise<EventsResponse> {
  return getJson<EventsResponse>(eventsUrl(query), 'Could not load projects and events');
}
