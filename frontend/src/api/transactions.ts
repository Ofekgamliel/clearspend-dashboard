import { getJson, postJson } from './client.ts';
import type {
  TransactionEventRequest,
  TransactionEventResponse,
  TransactionCategoryRequest,
  TransactionCategoryResponse,
  TransactionAdjustmentRequest,
  TransactionAdjustmentResponse,
  TransactionsQuery,
  TransactionsResponse,
} from './contracts.ts';

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

export function saveTransactionEvent(
  request: TransactionEventRequest,
): Promise<TransactionEventResponse> {
  return postJson<TransactionEventResponse, TransactionEventRequest>(
    '/api/transaction-event',
    request,
    'Could not update event assignment',
  );
}

export function saveTransactionCategory(
  request: TransactionCategoryRequest,
): Promise<TransactionCategoryResponse> {
  return postJson<TransactionCategoryResponse, TransactionCategoryRequest>(
    '/api/transaction-category',
    request,
    'Could not save category correction',
  );
}

export function saveTransactionAdjustment(
  request: TransactionAdjustmentRequest,
): Promise<TransactionAdjustmentResponse> {
  return postJson<TransactionAdjustmentResponse, TransactionAdjustmentRequest>(
    '/api/transaction-adjustment',
    request,
    'Could not save spending adjustment',
  );
}
