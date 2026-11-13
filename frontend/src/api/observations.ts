import { getJson, postJson } from './client.ts';
import type { ObservationReviewRequest, ObservationReviewResponse, ObservationsQuery, ObservationsResponse } from './contracts.ts';

export function observationsUrl(query: ObservationsQuery): string {
  const parameters = new URLSearchParams({
    period: query.period,
    card: query.card,
    month: query.month ?? '',
    income_hidden: String(query.incomeHidden),
  });
  return `/api/observations?${parameters.toString()}`;
}

export function getObservations(query: ObservationsQuery): Promise<ObservationsResponse> {
  return getJson<ObservationsResponse>(
    observationsUrl(query),
    'Could not load financial observations',
  );
}

export function saveObservationReview(body: ObservationReviewRequest): Promise<ObservationReviewResponse> {
  return postJson<ObservationReviewResponse, ObservationReviewRequest>(
    '/api/observation-review',
    body,
    'Could not save the observation review',
  );
}
