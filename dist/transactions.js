(function attachClearSpendTransactions(root, factory) {
  const transactions = factory();
  if (typeof module === 'object' && module.exports) module.exports = transactions;
  root.ClearSpendTransactions = transactions;
}(typeof globalThis !== 'undefined' ? globalThis : window, () => {
  const transactionColumns = [
    ['merchant', 'Merchant'],
    ['category', 'Category / subcategory'],
    ['card', 'Provider / card / source'],
    ['transaction_date', 'Transaction date'],
    ['billing_date', 'Billing date'],
    ['billing_month', 'Reporting month'],
    ['amount', 'Charged amount'],
    ['original_amount', 'Original amount'],
    ['transaction_type', 'Transaction type'],
    ['execution_method', 'Execution method'],
    ['voucher_number', 'Voucher'],
    ['exchange_rate', 'Exchange rate'],
    ['notes', 'Notes'],
  ];

  const transactionNumericKeys = new Set(['amount', 'original_amount', 'exchange_rate']);
  const transactionCollator = new Intl.Collator(['he', 'en'], {
    numeric: true,
    sensitivity: 'base',
  });
  const transactionTextValue = value => String(value ?? '').trim();

  function transactionSortValue(item, key) {
    if (key === 'merchant') {
      return `${transactionTextValue(item.merchant_display_name)} ${transactionTextValue(item.merchant_raw)} ${transactionTextValue(item.merchant_normalized)}`;
    }
    if (key === 'category') {
      return `${transactionTextValue(item.category)} ${transactionTextValue(item.subcategory)}`;
    }
    if (key === 'card') {
      return `${transactionTextValue(item.provider)} ${transactionTextValue(item.card_last4)} ${transactionTextValue(item.source_sheet)}`;
    }
    return item[key];
  }

  function sortedTransactionRows(rows, sort) {
    return [...rows].sort((left, right) => {
      const leftValue = transactionSortValue(left, sort.key);
      const rightValue = transactionSortValue(right, sort.key);
      const leftEmpty = leftValue === null || leftValue === undefined || leftValue === '';
      const rightEmpty = rightValue === null || rightValue === undefined || rightValue === '';
      if (leftEmpty || rightEmpty) {
        if (leftEmpty && rightEmpty) return 0;
        return leftEmpty ? 1 : -1;
      }
      const comparison = transactionNumericKeys.has(sort.key)
        ? Number(leftValue) - Number(rightValue)
        : transactionCollator.compare(String(leftValue), String(rightValue));
      return sort.direction === 'asc' ? comparison : -comparison;
    });
  }

  return {
    sortedTransactionRows,
    transactionColumns,
    transactionSortValue,
    transactionTextValue,
  };
}));
