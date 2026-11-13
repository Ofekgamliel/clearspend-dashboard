export class ApiError<TPayload = unknown> extends Error {
  readonly status: number;
  readonly payload: TPayload | null;
  readonly url: string;

  constructor(
    message: string,
    options: { status?: number; payload?: TPayload | null; url?: string } = {},
  ) {
    super(message);
    this.name = 'ApiError';
    this.status = options.status ?? 0;
    this.payload = options.payload ?? null;
    this.url = options.url ?? '';
  }
}

function payloadError(payload: unknown, fallbackMessage: string): string {
  if (typeof payload !== 'object' || payload === null || !('error' in payload)) {
    return fallbackMessage;
  }
  return typeof payload.error === 'string' && payload.error ? payload.error : fallbackMessage;
}

export async function requestJson<TResponse>(
  url: string,
  options: RequestInit = {},
  fallbackMessage = 'Could not load local data',
): Promise<TResponse> {
  const response = await fetch(url, options);
  let payload: unknown;
  try {
    payload = await response.json();
  } catch {
    throw new ApiError(fallbackMessage, { status: response.status, url });
  }
  if (!response.ok) {
    throw new ApiError(payloadError(payload, fallbackMessage), {
      status: response.status,
      payload,
      url,
    });
  }
  return payload as TResponse;
}

export function getJson<TResponse>(
  url: string,
  fallbackMessage?: string,
): Promise<TResponse> {
  return requestJson<TResponse>(url, { cache: 'no-store' }, fallbackMessage);
}

export function postJson<TResponse, TBody = unknown>(
  url: string,
  body: TBody,
  fallbackMessage?: string,
): Promise<TResponse> {
  return requestJson<TResponse>(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  }, fallbackMessage);
}

export function postForm<TResponse>(
  url: string,
  body: FormData,
  fallbackMessage?: string,
): Promise<TResponse> {
  return requestJson<TResponse>(url, { method: 'POST', body }, fallbackMessage);
}
