import type { EventSummary, EventTransaction, PeriodKey } from '../../api/contracts.ts';

export interface EventItem { kind: 'event'; event: EventSummary; start_date: string }
export interface EventGroupItem { kind: 'group'; id: string; destination: string; events: EventSummary[]; start_date: string }
export type EventPanelItem = EventItem | EventGroupItem;

export function isBusinessTrip(eventType: string): boolean { return eventType === 'business_trip'; }
export function destinationKey(destination: string | null): string { return String(destination ?? '').trim().toLocaleLowerCase('he'); }

export function buildEventPanelItems(events: EventSummary[], period: PeriodKey): EventPanelItem[] {
  const items: EventPanelItem[] = [];
  const groupedIds = new Set<number>();
  if (period !== 'month') {
    const destinations = new Map<string, EventSummary[]>();
    events.filter((event) => isBusinessTrip(event.event_type) && event.destination).forEach((event) => {
      const key = destinationKey(event.destination);
      destinations.set(key, [...(destinations.get(key) ?? []), event]);
    });
    [...destinations.values()].filter((group) => group.length > 1).forEach((group, index) => {
      group.forEach((event) => groupedIds.add(event.id));
      items.push({
        kind: 'group', id: `business-group-${index}`, destination: group[0]?.destination ?? '', events: group,
        start_date: group.reduce((earliest, event) => event.start_date < earliest ? event.start_date : earliest, group[0]?.start_date ?? ''),
      });
    });
  }
  events.filter((event) => !groupedIds.has(event.id)).forEach((event) => items.push({ kind: 'event', event, start_date: event.start_date }));
  return items.sort((left, right) => right.start_date.localeCompare(left.start_date));
}

export function categoryTotals(transactions: EventTransaction[]): Array<{ category: string; amount: number }> {
  const totals = new Map<string, number>();
  transactions.forEach((item) => totals.set(item.category, (totals.get(item.category) ?? 0) + Number(item.personal_amount || 0)));
  return [...totals.entries()].map(([category, amount]) => ({ category, amount })).sort((left, right) => right.amount - left.amount);
}

export function eventIcon(event: Pick<EventSummary, 'event_type' | 'icon'>): string {
  if (event.event_type === 'business_trip') return 'briefcase';
  return ({ plane: '✈', sun: '☀', home: '⌂', trip: '✈', celebration: '✦', other: '◆' } as Record<string, string>)[event.icon ?? '']
    ?? event.icon ?? ({ trip: '✈', celebration: '✦', other: '◆' } as Record<string, string>)[event.event_type] ?? '◆';
}
