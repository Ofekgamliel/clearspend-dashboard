import { getJson } from './client.ts';
import type { TransactionsQuery, TransactionsResponse } from './contracts.ts';

export function transactionsUrl(query: TransactionsQuery): string {
  const parameters = new URLSearchParams({
    period: query.period,
    month: query.month ?? '',
    card: query.card,
    q: query.search?.trim() ?? '',
    category: query.category ?? '',
    event_scope: query.eventScope ?? 'all',
  });
  return `/api/transactions?${parameters.toString()}`;
}

export function getTransactions(query: TransactionsQuery): Promise<TransactionsResponse> {
  return getJson<TransactionsResponse>(
    transactionsUrl(query),
    'Could not load transactions',
  );
}
