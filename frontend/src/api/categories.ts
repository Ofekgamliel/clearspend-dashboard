import { getJson } from './client';
import type { CategoriesQuery, CategoriesResponse } from './contracts';

export function categoriesUrl(query: CategoriesQuery): string {
  const parameters = new URLSearchParams({
    period: query.period,
    month: query.month ?? '',
    card: query.card,
    event_scope: query.eventScope,
  });
  return `/api/categories?${parameters.toString()}`;
}

export function getCategories(query: CategoriesQuery): Promise<CategoriesResponse> {
  return getJson<CategoriesResponse>(
    categoriesUrl(query),
    'Could not load categories',
  );
}
