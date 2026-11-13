(function attachClearSpendFormat(root, factory) {
  const format = factory();
  if (typeof module === 'object' && module.exports) module.exports = format;
  root.ClearSpendFormat = format;
}(typeof globalThis !== 'undefined' ? globalThis : window, () => {
  const money = value => new Intl.NumberFormat('en-IL', {
    style: 'currency',
    currency: 'ILS',
    maximumFractionDigits: 2,
  }).format(Number(value) || 0).replace('ILS', '₪');

  const compact = value => new Intl.NumberFormat('en', {
    notation: 'compact',
    maximumFractionDigits: 1,
  }).format(Number(value) || 0);

  const escapeHtml = value => String(value ?? '').replace(
    /[&<>'"]/g,
    character => ({
      '&': '&amp;',
      '<': '&lt;',
      '>': '&gt;',
      "'": '&#39;',
      '"': '&quot;',
    }[character]),
  );

  const formatDate = value => value
    ? new Intl.DateTimeFormat('en-GB', {
      day: 'numeric',
      month: 'short',
      year: '2-digit',
    }).format(new Date(`${value}T12:00:00`))
    : '—';

  const formatDateTime = value => value
    ? new Intl.DateTimeFormat('en-GB', {
      day: 'numeric',
      month: 'short',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    }).format(new Date(value.replace(' ', 'T')))
    : '—';

  const formatMonth = value => value
    ? new Intl.DateTimeFormat('en-GB', {
      month: 'long',
      year: 'numeric',
    }).format(new Date(`${value}-01T12:00:00`))
    : 'Latest month';

  const median = values => {
    const sorted = values.map(Number).filter(Number.isFinite).sort((left, right) => left - right);
    if (!sorted.length) return 0;
    const middle = Math.floor(sorted.length / 2);
    return sorted.length % 2 ? sorted[middle] : (sorted[middle - 1] + sorted[middle]) / 2;
  };

  const shiftMonth = (value, offset) => {
    const [year, month] = value.split('-').map(Number);
    const date = new Date(year, month - 1 + offset, 1, 12);
    return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}`;
  };

  const monthLabel = value => value
    ? new Intl.DateTimeFormat('en-GB', {
      month: 'short',
      year: 'numeric',
    }).format(new Date(`${value}-01T12:00:00`))
    : '—';

  const monthRange = months => {
    const values = [...new Set(months.filter(Boolean))].sort();
    return values.length < 2
      ? monthLabel(values[0])
      : `${monthLabel(values[0])} – ${monthLabel(values.at(-1))}`;
  };

  return {
    compact,
    escapeHtml,
    formatDate,
    formatDateTime,
    formatMonth,
    median,
    money,
    monthLabel,
    monthRange,
    shiftMonth,
  };
}));
