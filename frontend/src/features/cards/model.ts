import type { DashboardCard } from '../../api/contracts';

export function cardShareWidth(share: number): number {
  return Math.min(Math.max(Number(share) || 0, 0), 100);
}

export function cardProviderClass(card: DashboardCard): 'mastercard' | 'standard' {
  return card.provider.toLowerCase() === 'max' ? 'mastercard' : 'standard';
}

export function cardTransactionLabel(count: number): string {
  return `${new Intl.NumberFormat('en-US', { maximumFractionDigits: 0 }).format(Number(count) || 0)} trx`;
}
