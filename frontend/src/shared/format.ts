const moneyFormatter = new Intl.NumberFormat('en-IL', {
  style: 'currency',
  currency: 'ILS',
  maximumFractionDigits: 2,
});

const decimalFormatter = new Intl.NumberFormat('en-IL', {
  maximumFractionDigits: 2,
});

function finiteNumber(value: number): number {
  return Number.isFinite(Number(value)) ? Number(value) : 0;
}

export function formatMoney(value: number): string {
  return moneyFormatter.format(finiteNumber(value));
}

export function formatSourceAmount(value: number | null, currency: string | null): string {
  if (value === null || !Number.isFinite(Number(value))) return '—';
  return `${decimalFormatter.format(Number(value))} ${currency ?? ''}`.trim();
}

export function formatPercent(value: number): string {
  return `${finiteNumber(value).toFixed(1).replace(/\.0$/, '')}%`;
}

export function formatInteger(value: number): string {
  return new Intl.NumberFormat('en-US', { maximumFractionDigits: 0 }).format(Number(value) || 0);
}

export function formatCompact(value: number): string {
  return new Intl.NumberFormat('en', {
    notation: 'compact',
    maximumFractionDigits: 1,
  }).format(Number(value) || 0);
}

export function formatDate(value: string): string {
  if (!value) return '—';
  return new Intl.DateTimeFormat('en-GB', {
    day: 'numeric',
    month: 'short',
    year: '2-digit',
    timeZone: 'UTC',
  }).format(new Date(`${value}T12:00:00Z`));
}

export function formatMonth(month: string | null): string {
  if (!month || !/^\d{4}-\d{2}$/.test(month)) return 'the previous month';
  const [year, monthNumber] = month.split('-').map(Number);
  return new Intl.DateTimeFormat('en', {
    month: 'long',
    year: 'numeric',
    timeZone: 'UTC',
  }).format(new Date(Date.UTC(year, monthNumber - 1, 1)));
}

export function formatShortMonth(month: string | null): string {
  if (!month || !/^\d{4}-\d{2}$/.test(month)) return '';
  const [year, monthNumber] = month.split('-').map(Number);
  return new Intl.DateTimeFormat('en-GB', {
    month: 'short',
    year: 'numeric',
    timeZone: 'UTC',
  }).format(new Date(Date.UTC(year, monthNumber - 1, 1)));
}
