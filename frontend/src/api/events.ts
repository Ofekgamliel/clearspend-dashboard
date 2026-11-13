import { getJson, postJson } from './client.ts';
import type { CreateEventRequest, CreateEventResponse, EventsQuery, EventsResponse, SaveEventRequest, SaveEventResponse } from './contracts.ts';

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

export function createEvent(request: CreateEventRequest): Promise<CreateEventResponse> {
  return postJson<CreateEventResponse, CreateEventRequest>(
    '/api/events',
    request,
    'Could not create event',
  );
}

export function saveEvent(request: SaveEventRequest): Promise<SaveEventResponse> {
  return postJson<SaveEventResponse, SaveEventRequest>(
    '/api/event-settings',
    request,
    'Could not save event',
  );
}
