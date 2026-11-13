(function attachClearSpendImportReview(root, factory) {
  const review = factory();
  if (typeof module === 'object' && module.exports) module.exports = review;
  root.ClearSpendImportReview = review;
}(typeof globalThis !== 'undefined' ? globalThis : window, () => {
  const importStepNames = ['Files', 'Checks', 'Merchants', 'Reconcile', 'Approve'];
  const decisionValues = decisions => decisions instanceof Map
    ? [...decisions.values()]
    : [...(decisions || [])];

  function requiresManualReconciliation(file) {
    return file.kind === 'statement'
      && file.status === 'ready'
      && ['manual_required', 'mismatch'].includes(file.reconciliation?.status);
  }

  function manualReconciliationFiles(files) {
    return (files || []).filter(requiresManualReconciliation);
  }

  function invalidMerchantDecisions(decisions) {
    return decisionValues(decisions).filter(item => !['needs_review', 'exclude'].includes(item.resolution)
      && (!item.category
        || item.category === 'Needs review'
        || (item.resolution === 'link' && !item.canonical_group_id)));
  }

  function unresolvedDuplicateDecisions(possibleDuplicates, duplicateDecisions) {
    return (possibleDuplicates || []).filter(item => !['skip', 'import'].includes(
      duplicateDecisions?.get(item.candidate_id),
    ));
  }

  function merchantDecision(merchant, suggestion) {
    if (suggestion) {
      return {
        merchant_normalized: merchant.merchant_normalized,
        resolution: 'link',
        category: suggestion.category_status === 'unanimous' ? suggestion.category : 'Needs review',
        display_name: suggestion.display_name,
        canonical_group_id: suggestion.canonical_group_id,
        scope: 'exact',
        suggested_match: true,
      };
    }
    return {
      merchant_normalized: merchant.merchant_normalized,
      resolution: merchant.provider_category ? 'provider' : 'needs_review',
      category: merchant.provider_category || 'Needs review',
      display_name: merchant.display_name || merchant.merchant_raw,
      canonical_group_id: merchant.canonical_group_id || '',
      scope: merchant.provider_category ? 'exact' : 'batch',
    };
  }

  function importPreviewRows(batch, decisions, duplicateDecisions) {
    const excluded = new Set(decisionValues(decisions)
      .filter(item => item.resolution === 'exclude')
      .map(item => item.merchant_normalized));
    const confirmed = (batch?.new_transactions || [])
      .filter(item => !excluded.has(item.merchant_normalized));
    const reviewed = (batch?.possible_duplicates || [])
      .filter(item => duplicateDecisions?.get(item.candidate_id) === 'import'
        && !excluded.has(item.merchant_normalized))
      .map(item => ({ ...item, reviewed_new: true }));
    return [...confirmed, ...reviewed].sort((left, right) => String(
      right.billing_date || right.transaction_date || '',
    ).localeCompare(String(left.billing_date || left.transaction_date || ''))
      || String(left.merchant || '').localeCompare(String(right.merchant || '')));
  }

  function importPreviewIdentity(row, decisions, merchants) {
    const decision = decisions?.get(row.merchant_normalized);
    const merchant = (merchants || [])
      .find(item => item.merchant_normalized === row.merchant_normalized);
    return {
      display: decision?.display_name || merchant?.display_name || row.merchant,
      category: decision?.category || merchant?.category || 'Needs review',
    };
  }

  function importPreviewStatus(row) {
    if (row.reviewed_new) return ['Reviewed as new', 'amber'];
    if (row.source_status === 'pending') return ['Pending · not final', 'amber'];
    if (row.source_status === 'outside_cycle') return ['Outside billing cycle', 'purple'];
    if (row.installment_number) {
      return [`Installment ${row.installment_number}${row.installment_total ? `/${row.installment_total}` : ''}`, 'purple'];
    }
    return ['Confirmed new', ''];
  }

  return {
    importPreviewIdentity,
    importPreviewRows,
    importPreviewStatus,
    importStepNames,
    invalidMerchantDecisions,
    manualReconciliationFiles,
    merchantDecision,
    requiresManualReconciliation,
    unresolvedDuplicateDecisions,
  };
}));
