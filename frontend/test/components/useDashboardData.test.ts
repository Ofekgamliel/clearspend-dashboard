import { flushPromises, mount } from '@vue/test-utils';
import { defineComponent, nextTick } from 'vue';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import type { DashboardResponse } from '../../src/api/contracts';
import { useDashboardData } from '../../src/features/dashboard/useDashboardData';

const getDashboard = vi.fn();
const getRuntimeHealth = vi.fn();

vi.mock('../../src/api/dashboard', () => ({
  getDashboard: (...args: unknown[]) => getDashboard(...args),
}));
vi.mock('../../src/api/runtime', async (importOriginal) => {
  const original = await importOriginal<typeof import('../../src/api/runtime')>();
  return { ...original, getRuntimeHealth: (...args: unknown[]) => getRuntimeHealth(...args) };
});

function deferred<T>() {
  let resolve!: (value: T) => void;
  const promise = new Promise<T>((done) => { resolve = done; });
  return { promise, resolve };
}

function dashboard(period: 'month' | 'year'): DashboardResponse {
  return {
    period: { key: period, label: period, start: '2027-01-01', end: '2027-01-31' },
    selected_card: 'all', cards: [], available_months: ['2027-01'],
    metrics: { spent: 0, refunds: 0, transactions: 0, daily_average: 0, active_days: 0 },
    income_summary: {
      has_income: false, income: 0, spending: 0, charges: 0, refunds: 0,
      remaining: 0, remaining_percentage: null, spent_percentage: null, scope: 'all_cards',
      averages: { spending: 0, amount_left: 0, spending_months: 0, amount_left_months: 0, start_month: null, end_month: null, current_month_partial: false },
    },
    categories: [], category_comparison: { previous_month: null, status: 'unavailable' },
    trend: [], trend_mode: period === 'month' ? 'purchase_activity' : 'billing_summary',
    purchase_activity_summary: null, recent_transactions: [], latest_import: null,
  } as DashboardResponse;
}

function mountComposable() {
  return mount(defineComponent({
    setup() { return useDashboardData(); },
    template: '<div />',
  }));
}

describe('useDashboardData loading contract', () => {
  beforeEach(() => {
    getDashboard.mockReset();
    getRuntimeHealth.mockReset();
    getRuntimeHealth.mockResolvedValue({ status: 'ok', mode: 'local', database: true, api_compatibility: 'clearspend-vue-api-v2' });
  });

  it('ends runtime checking before the initial dashboard response settles', async () => {
    const pending = deferred<DashboardResponse>();
    getDashboard.mockReturnValueOnce(pending.promise);
    const wrapper = mountComposable();
    await flushPromises();

    expect(wrapper.vm.runtimeReady).toBe(true);
    expect(wrapper.vm.runtimeChecking).toBe(false);
    expect(wrapper.vm.loadMode).toBe('initial');
    expect(wrapper.vm.displayDashboard).toBeNull();

    pending.resolve(dashboard('month'));
    await flushPromises();
    expect(wrapper.vm.displayDashboard?.period.key).toBe('month');
  });

  it('hides an old-scope response immediately but retains matching data during refresh', async () => {
    getDashboard.mockResolvedValueOnce(dashboard('month'));
    const wrapper = mountComposable();
    await flushPromises();

    const changed = deferred<DashboardResponse>();
    getDashboard.mockReturnValueOnce(changed.promise);
    wrapper.vm.period = 'year';
    await nextTick();
    expect(wrapper.vm.displayDashboard).toBeNull();
    expect(wrapper.vm.loadMode).toBe('scope-change');

    changed.resolve(dashboard('year'));
    await flushPromises();
    const refreshed = deferred<DashboardResponse>();
    getDashboard.mockReturnValueOnce(refreshed.promise);
    wrapper.vm.refresh();
    expect(wrapper.vm.displayDashboard?.period.key).toBe('year');
    expect(wrapper.vm.loadMode).toBe('refresh');
  });

  it('distinguishes blocking failures from refresh failures with matching content', async () => {
    getDashboard.mockRejectedValueOnce(new Error('Initial dashboard failed'));
    const blocked = mountComposable();
    await flushPromises();
    expect(blocked.vm.displayDashboard).toBeNull();
    expect(blocked.vm.loadErrorMode).toBe('blocking');

    getDashboard.mockReset();
    getDashboard.mockResolvedValueOnce(dashboard('month'));
    const refreshing = mountComposable();
    await flushPromises();
    getDashboard.mockRejectedValueOnce(new Error('Refresh failed'));
    refreshing.vm.refresh();
    await flushPromises();
    expect(refreshing.vm.displayDashboard?.period.key).toBe('month');
    expect(refreshing.vm.loadErrorMode).toBe('refresh');
    expect(refreshing.vm.loadError).toBe('Refresh failed');
  });

  it('retries a failed same-scope refresh without discarding matching content', async () => {
    getDashboard.mockResolvedValueOnce(dashboard('month'));
    const wrapper = mountComposable();
    await flushPromises();

    getDashboard.mockRejectedValueOnce(new Error('Refresh failed'));
    wrapper.vm.refresh();
    await flushPromises();
    expect(wrapper.vm.displayDashboard?.period.key).toBe('month');
    expect(wrapper.vm.loadErrorMode).toBe('refresh');

    const retry = deferred<DashboardResponse>();
    getDashboard.mockReturnValueOnce(retry.promise);
    wrapper.vm.retry();
    expect(wrapper.vm.loadMode).toBe('refresh');
    expect(wrapper.vm.displayDashboard?.period.key).toBe('month');
    expect(wrapper.vm.loadError).toBe('');

    retry.resolve(dashboard('month'));
    await flushPromises();
    expect(wrapper.vm.loadMode).toBe('idle');
    expect(wrapper.vm.loadErrorMode).toBeNull();
  });
});
