(function attachClearSpendCategories(root, factory) {
  const categories = factory();
  if (typeof module === 'object' && module.exports) module.exports = categories;
  root.ClearSpendCategories = categories;
}(typeof globalThis !== 'undefined' ? globalThis : window, () => {
  function buildCategorySegments(categories, colors) {
    const gradientStops = [];
    let cursor = 0;
    const segments = categories.map((category, index) => {
      const start = Math.min(cursor, 100);
      cursor = Math.min(cursor + category.share, 100);
      gradientStops.push(`${colors[index % colors.length]} ${start}% ${cursor}%`);
      return { ...category, start, end: cursor };
    });
    if (cursor < 100) gradientStops.push(`#ececf1 ${cursor}% 100%`);
    return {
      ariaLabel: categories.map(category => `${category.category}: ${category.share}%`).join(', '),
      gradient: `conic-gradient(${gradientStops.join(',')})`,
      segments,
    };
  }

  function categorySegmentAt(segments, percentage) {
    return segments.find(item => percentage >= item.start && percentage < item.end);
  }

  function donutPercentageAt(x, y) {
    const angle = (Math.atan2(y, x) * 180 / Math.PI + 450) % 360;
    return angle / 3.6;
  }

  function categoryComparisonModel(category, comparison) {
    if (!comparison?.previous_month) return null;
    const status = category.comparison || 'unavailable';
    const labels = {
      up: `↑ ${Math.abs(Number(category.change_percent))}%`,
      down: `↓ ${Math.abs(Number(category.change_percent))}%`,
      same: '0%',
      new: 'New',
      unavailable: '—',
    };
    return {
      label: labels[status] || '—',
      previousMonth: comparison.previous_month,
      status,
    };
  }

  return {
    buildCategorySegments,
    categoryComparisonModel,
    categorySegmentAt,
    donutPercentageAt,
  };
}));
