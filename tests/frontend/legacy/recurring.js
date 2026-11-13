(function attachClearSpendRecurring(root, factory) {
  const recurring = factory();
  if (typeof module === 'object' && module.exports) module.exports = recurring;
  root.ClearSpendRecurring = recurring;
}(typeof globalThis !== 'undefined' ? globalThis : window, () => {
  const recurringTypeOptions = [
    'Fixed recurring',
    'Usage-based recurring',
    'Scheduled obligation',
    'Other recurring',
  ];
  const recurringCadenceOptions = [
    'Weekly',
    'Monthly',
    'Every 2 months',
    'Quarterly',
    'Every 6 months',
    'Yearly',
    'Custom',
    'Irregular',
    'Unknown',
  ];
  const recurringStatusLabels = {
    confirmed: 'Confirmed', variable: 'Variable', expected: 'Expected', missing: 'Missing',
    increased: 'Increased', paid: 'Paid', upcoming: 'Upcoming', due: 'Due',
    overdue: 'Overdue', active: 'Active', ended: 'Ended', paused: 'Paused',
    unknown: 'Unknown', completed: 'Completed',
  };
  const recurringColumns = {
    series: [
      ['display_name', 'Merchant'], ['category', 'Category'], ['recurring_type', 'Type'],
      ['cadence', 'Cadence'], ['amount', 'Amount'], ['coverage', 'Expected / coverage'],
      ['status', 'Status'],
    ],
    commitments: [
      ['display_name', 'Purchase'], ['category', 'Category'],
      ['current_installment', 'Progress'], ['paid', 'Paid'], ['remaining', 'Remaining'],
      ['status', 'Status'],
    ],
  };
  const recurringNumericKeys = new Set(['amount', 'current_installment', 'paid', 'remaining']);
  const recurringCollator = new Intl.Collator(['he', 'en'], { numeric: true, sensitivity: 'base' });

  const recurringStatusClass = value => ['missing', 'increased', 'due', 'overdue', 'unknown'].includes(value)
    ? 'amber'
    : ['ended', 'paused', 'completed'].includes(value) ? 'gray' : '';

  function sortedRecurringRows(rows, sort) {
    return [...rows].sort((left, right) => {
      const leftValue = left[sort.key];
      const rightValue = right[sort.key];
      const leftEmpty = leftValue === null || leftValue === undefined || leftValue === '';
      const rightEmpty = rightValue === null || rightValue === undefined || rightValue === '';
      if (leftEmpty || rightEmpty) {
        if (leftEmpty && rightEmpty) return 0;
        return leftEmpty ? 1 : -1;
      }
      const comparison = recurringNumericKeys.has(sort.key)
        ? Number(leftValue) - Number(rightValue)
        : recurringCollator.compare(String(leftValue), String(rightValue));
      return sort.direction === 'asc' ? comparison : -comparison;
    });
  }

  return {
    recurringCadenceOptions,
    recurringColumns,
    recurringStatusClass,
    recurringStatusLabels,
    recurringTypeOptions,
    sortedRecurringRows,
  };
}));
