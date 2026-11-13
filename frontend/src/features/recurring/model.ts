import type { InstallmentCommitment, RecurringSeries } from '../../api/contracts.ts';

export type RecurringTab = 'series' | 'commitments' | 'verdicts';
export type RecurringRow = RecurringSeries | InstallmentCommitment;
export type RecurringSortKey = keyof RecurringSeries | keyof InstallmentCommitment;
export interface RecurringSort { key: RecurringSortKey; direction: 'asc' | 'desc' }

const numericKeys = new Set<RecurringSortKey>(['amount', 'current_installment', 'paid', 'remaining']);
const collator = new Intl.Collator(['he', 'en'], { numeric: true, sensitivity: 'base' });

export const recurringStatusLabels: Record<string, string> = {
  confirmed: 'Confirmed', variable: 'Variable', expected: 'Expected', missing: 'Missing',
  increased: 'Increased', paid: 'Paid', upcoming: 'Upcoming', due: 'Due',
  overdue: 'Overdue', active: 'Active', ended: 'Ended', paused: 'Paused',
  unknown: 'Unknown', completed: 'Completed',
};

export function recurringStatusClass(status: string): 'amber' | 'gray' | '' {
  if (['missing', 'increased', 'due', 'overdue', 'unknown'].includes(status)) return 'amber';
  if (['ended', 'paused', 'completed'].includes(status)) return 'gray';
  return '';
}

export function burdenShares(recurring: number, installments: number) {
  const recurringShare = Math.min(100, Math.max(0, Number(recurring) || 0));
  const installmentShare = Math.min(100 - recurringShare, Math.max(0, Number(installments) || 0));
  return { recurring: recurringShare, installments: installmentShare, other: Math.max(0, 100 - recurringShare - installmentShare) };
}

export function sortRecurring<T extends RecurringRow>(rows: T[], sort: RecurringSort): T[] {
  return [...rows].sort((left, right) => {
    const leftValue = left[sort.key as keyof T];
    const rightValue = right[sort.key as keyof T];
    const leftEmpty = leftValue === null || leftValue === undefined || leftValue === '';
    const rightEmpty = rightValue === null || rightValue === undefined || rightValue === '';
    if (leftEmpty || rightEmpty) {
      if (leftEmpty && rightEmpty) return 0;
      return leftEmpty ? 1 : -1;
    }
    const comparison = numericKeys.has(sort.key)
      ? Number(leftValue) - Number(rightValue)
      : collator.compare(String(leftValue), String(rightValue));
    return sort.direction === 'asc' ? comparison : -comparison;
  });
}

export function nextRecurringSort(current: RecurringSort, key: RecurringSortKey): RecurringSort {
  return current.key === key
    ? { key, direction: current.direction === 'asc' ? 'desc' : 'asc' }
    : { key, direction: 'asc' };
}
