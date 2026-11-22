import { flushPromises, mount } from '@vue/test-utils';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import type { CategoriesResponse, EventsResponse, ObservationsResponse, RecurringResponse } from '../../src/api/contracts';
import CategoriesPanel from '../../src/features/categories/CategoriesPanel.vue';
import EventsPanel from '../../src/features/events/EventsPanel.vue';
import ObservationsPanel from '../../src/features/observations/ObservationsPanel.vue';
import RecurringPanel from '../../src/features/recurring/RecurringPanel.vue';

const getCategories = vi.fn();
const getEvents = vi.fn();
const getObservations = vi.fn();
const getRecurring = vi.fn();

vi.mock('../../src/api/categories', () => ({ getCategories: (...args: unknown[]) => getCategories(...args) }));
vi.mock('../../src/api/events', () => ({
  getEvents: (...args: unknown[]) => getEvents(...args),
  createEvent: vi.fn(),
  saveEvent: vi.fn(),
}));
vi.mock('../../src/api/observations', () => ({
  getObservations: (...args: unknown[]) => getObservations(...args),
  saveObservationReview: vi.fn(),
}));
vi.mock('../../src/api/recurring', () => ({
  getRecurring: (...args: unknown[]) => getRecurring(...args),
  saveRecurringProfile: vi.fn(),
}));

const reportingPeriod = { key: 'month' as const, start: '2027-01-01', end: '2027-01-31', label: 'January 2027' };
const categoriesResponse: CategoriesResponse = {
  period: reportingPeriod,
  selected_card: 'all',
  event_scope: 'all',
  total: 42,
  categories: [{ category: 'Synthetic category', amount: 42, transactions: 1, merchants: 1, share: 100 }],
  category_comparison: { available: false, previous_month: null },
};
const eventsResponse: EventsResponse = { period: reportingPeriod, selected_card: 'all', events: [], available_events: [] };
const observationsResponse: ObservationsResponse = {
  period: 'month', selectedCard: 'all', selectedMonth: '2027-01', observedStart: '2027-01-01', observedEnd: '2027-01-31',
  historical: false, findingCount: 0, typeCount: 0, findings: [], groups: [],
};
const recurringResponse: RecurringResponse = {
  period: reportingPeriod,
  selected_card: 'all',
  metrics: {
    recurring_billed: 0, recurring_average: 0, active_series: 0, needs_attention: 0, installment_billed: 0,
    installment_average: 0, installment_plans: 0, recurring_share: 0, installment_share: 0,
  },
  series: [], commitments: [], trend: [], verdict_summary: { reviewed: 0, recurring: 0, not_recurring: 0, unresolved: 0 },
};

describe('independent dashboard panel refresh failures', () => {
  beforeEach(() => {
    getCategories.mockReset();
    getEvents.mockReset();
    getObservations.mockReset();
    getRecurring.mockReset();
  });

  it('retains Categories content and exposes retry', async () => {
    getCategories.mockResolvedValueOnce(categoriesResponse).mockRejectedValueOnce(new Error('Categories refresh failed'));
    const wrapper = mount(CategoriesPanel, { props: { period: 'month', month: '2027-01', card: 'all', refreshKey: 0 } });
    await flushPromises();
    await wrapper.setProps({ refreshKey: 1 });
    await flushPromises();
    expect(wrapper.text()).toContain('Synthetic category');
    expect(wrapper.find('.categories-skeleton').exists()).toBe(false);
    expect(wrapper.find('[role="alert"]').text()).toContain('Categories refresh failed');
    expect(wrapper.find('[role="alert"] button').text()).toBe('Retry');
  });

  it('retains Events content and exposes retry', async () => {
    getEvents.mockResolvedValueOnce(eventsResponse).mockRejectedValueOnce(new Error('Events refresh failed'));
    const wrapper = mount(EventsPanel, { props: { period: 'month', month: '2027-01', card: 'all', refreshKey: 0 } });
    await flushPromises();
    await wrapper.setProps({ refreshKey: 1 });
    await flushPromises();
    expect(wrapper.text()).toContain('No active projects');
    expect(wrapper.find('.events-skeleton').exists()).toBe(false);
    expect(wrapper.find('[role="alert"]').text()).toContain('Events refresh failed');
  });

  it('retains Observations content and exposes retry', async () => {
    getObservations.mockResolvedValueOnce(observationsResponse).mockRejectedValueOnce(new Error('Observations refresh failed'));
    const wrapper = mount(ObservationsPanel, { props: { period: 'month', month: '2027-01', card: 'all', incomeHidden: false, refreshKey: 0 } });
    await flushPromises();
    await wrapper.setProps({ refreshKey: 1 });
    await flushPromises();
    expect(wrapper.text()).toContain('No observations');
    expect(wrapper.find('.observations-skeleton').exists()).toBe(false);
    expect(wrapper.find('[role="alert"]').text()).toContain('Observations refresh failed');
  });

  it('retains Recurring content and keeps its details action available', async () => {
    getRecurring.mockResolvedValueOnce(recurringResponse).mockRejectedValueOnce(new Error('Recurring refresh failed'));
    const wrapper = mount(RecurringPanel, { props: { period: 'month', month: '2027-01', card: 'all', refreshKey: 0 } });
    await flushPromises();
    await wrapper.setProps({ refreshKey: 1 });
    await flushPromises();
    expect(wrapper.find('.recurring-skeleton').exists()).toBe(false);
    expect(wrapper.find('[role="alert"]').text()).toContain('Recurring refresh failed');
    expect(wrapper.get('header > button').attributes('disabled')).toBeUndefined();
  });
});
