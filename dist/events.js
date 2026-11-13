(function attachClearSpendEvents(root, factory) {
  const events = factory();
  if (typeof module === 'object' && module.exports) module.exports = events;
  root.ClearSpendEvents = events;
}(typeof globalThis !== 'undefined' ? globalThis : window, () => {
  const isBusinessTrip = eventType => eventType === 'business_trip';

  function eventDateValidationMessage(values) {
    return values.end_date < values.start_date
      ? 'End date cannot be before the start date.'
      : '';
  }

  function destinationKey(destination) {
    return String(destination || '').trim().toLocaleLowerCase('he');
  }

  function buildEventPanelItems(events, period) {
    const items = [];
    const groups = new Map();
    const groupedIds = new Set();
    if (period !== 'month') {
      const byDestination = new Map();
      events
        .filter(event => isBusinessTrip(event.event_type) && event.destination)
        .forEach(event => {
          const key = destinationKey(event.destination);
          if (!byDestination.has(key)) byDestination.set(key, []);
          byDestination.get(key).push(event);
        });
      [...byDestination.entries()]
        .filter(([, destinationEvents]) => destinationEvents.length > 1)
        .forEach(([, destinationEvents], index) => {
          const id = `business-group-${index}`;
          groups.set(id, destinationEvents);
          destinationEvents.forEach(event => groupedIds.add(event.id));
          items.push({
            kind: 'group',
            id,
            destination: destinationEvents[0].destination,
            events: destinationEvents,
            start_date: destinationEvents.reduce(
              (value, event) => value < event.start_date ? value : event.start_date,
              destinationEvents[0].start_date,
            ),
          });
        });
    }
    events
      .filter(event => !groupedIds.has(event.id))
      .forEach(event => items.push({ kind: 'event', event, start_date: event.start_date }));
    items.sort((left, right) => String(right.start_date).localeCompare(String(left.start_date)));
    return { groups, items };
  }

  return {
    buildEventPanelItems,
    destinationKey,
    eventDateValidationMessage,
    isBusinessTrip,
  };
}));
