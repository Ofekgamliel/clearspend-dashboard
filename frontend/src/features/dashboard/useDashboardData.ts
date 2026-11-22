import { computed, onMounted, ref, watch } from 'vue';
import { getDashboard } from '../../api/dashboard';
import { getRuntimeHealth, runtimeCompatibilityError } from '../../api/runtime';
import type { DashboardResponse, PeriodKey } from '../../api/contracts';
import { selectedMonth } from '../filters/model';

export type DashboardLoadMode = 'idle' | 'initial' | 'scope-change' | 'refresh';
export type DashboardErrorMode = 'blocking' | 'refresh' | null;

export function dashboardScopeKey(period: PeriodKey, month: string, card: string): string {
  return JSON.stringify([period, month, card]);
}

export function useDashboardData() {
  const period = ref<PeriodKey>('month');
  const month = ref('');
  const card = ref('all');
  const dashboard = ref<DashboardResponse | null>(null);
  const responseScopeKey = ref<string | null>(null);
  const loadMode = ref<DashboardLoadMode>('idle');
  const loadError = ref('');
  const loadErrorMode = ref<DashboardErrorMode>(null);
  const runtimeChecking = ref(true);
  const runtimeReady = ref(false);
  const runtimeError = ref('');
  const revision = ref(0);
  let requestId = 0;

  const selectedScopeKey = computed(() => dashboardScopeKey(period.value, month.value, card.value));
  const displayDashboard = computed(() => (
    responseScopeKey.value === selectedScopeKey.value ? dashboard.value : null
  ));
  const loading = computed(() => loadMode.value !== 'idle');

  const effectiveMonth = computed(() => selectedMonth(
    month.value,
    dashboard.value?.period.start ?? null,
    dashboard.value?.available_months ?? [],
  ));

  async function load(mode: Exclude<DashboardLoadMode, 'idle'> = 'scope-change'): Promise<void> {
    const currentRequest = ++requestId;
    const requestScopeKey = selectedScopeKey.value;
    loadMode.value = mode;
    loadError.value = '';
    loadErrorMode.value = null;
    try {
      const response = await getDashboard({ period: period.value, month: month.value, card: card.value });
      if (currentRequest !== requestId) return;
      dashboard.value = response;
      responseScopeKey.value = requestScopeKey;
      if (card.value !== 'all' && !response.cards.some((item) => item.key === card.value)) card.value = 'all';
    } catch (caught) {
      if (currentRequest !== requestId) return;
      loadError.value = caught instanceof Error ? caught.message : 'Could not load dashboard filters';
      loadErrorMode.value = mode === 'refresh' && responseScopeKey.value === requestScopeKey
        ? 'refresh'
        : 'blocking';
    } finally {
      if (currentRequest === requestId) loadMode.value = 'idle';
    }
  }

  async function verifyRuntime(): Promise<void> {
    runtimeChecking.value = true;
    runtimeReady.value = false;
    runtimeError.value = '';
    try {
      const compatibilityError = runtimeCompatibilityError(await getRuntimeHealth());
      if (compatibilityError) throw new Error(compatibilityError);
      runtimeReady.value = true;
      runtimeChecking.value = false;
      void load('initial');
    } catch (caught) {
      const message = caught instanceof Error ? caught.message : '';
      runtimeError.value = /different builds|database is unavailable|server is not ready/i.test(message)
        ? message
        : 'Could not connect to the compatible local ClearSpend server. Start or restart it from this branch, then try again.';
    } finally {
      if (!runtimeReady.value) runtimeChecking.value = false;
    }
  }

  function changeMonth(value: string): void {
    month.value = value;
    period.value = 'month';
  }

  function refresh(): void {
    revision.value += 1;
    void load('refresh');
  }

  function retry(): void {
    if (loadErrorMode.value === 'refresh') {
      void load('refresh');
      return;
    }
    void load(dashboard.value ? 'scope-change' : 'initial');
  }

  watch([period, month, card], () => { if (runtimeReady.value) void load('scope-change'); });
  onMounted(() => { void verifyRuntime(); });

  return {
    period,
    month,
    card,
    dashboard,
    displayDashboard,
    loading,
    loadMode,
    loadError,
    loadErrorMode,
    selectedScopeKey,
    responseScopeKey,
    runtimeChecking,
    runtimeReady,
    runtimeError,
    revision,
    effectiveMonth,
    load,
    verifyRuntime,
    changeMonth,
    refresh,
    retry,
  };
}
