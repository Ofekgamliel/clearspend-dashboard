import type { DashboardMetrics } from '../../api/contracts';

export interface MetricContext {
  transactionNote: string;
  activeDaysNote: string;
}

export function metricContext(metrics: DashboardMetrics): MetricContext {
  const transactions = new Intl.NumberFormat('en-US', {
    maximumFractionDigits: 0,
  }).format(Number(metrics.transactions) || 0);
  return {
    transactionNote: `Calculated from ${transactions} imported transactions`,
    activeDaysNote: `across ${Number(metrics.active_days) || 0} active days`,
  };
}
