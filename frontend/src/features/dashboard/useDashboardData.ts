import { computed, onMounted, ref, watch } from 'vue';
import { getDashboard } from '../../api/dashboard';
import { getRuntimeHealth, runtimeCompatibilityError } from '../../api/runtime';
import type { DashboardResponse, PeriodKey } from '../../api/contracts';
import { selectedMonth } from '../filters/model';

export function useDashboardData() {
  const period = ref<PeriodKey>('month');
  const month = ref('');
  const card = ref('all');
  const dashboard = ref<DashboardResponse | null>(null);
  const loading = ref(true);
  const loadError = ref('');
  const runtimeChecking = ref(true);
  const runtimeReady = ref(false);
  const runtimeError = ref('');
  const revision = ref(0);
  let requestId = 0;

  const effectiveMonth = computed(() => selectedMonth(
    month.value,
    dashboard.value?.period.start ?? null,
    dashboard.value?.available_months ?? [],
  ));

  async function load(): Promise<void> {
    const currentRequest = ++requestId;
    loading.value = true;
    loadError.value = '';
    try {
      const response = await getDashboard({ period: period.value, month: month.value, card: card.value });
      if (currentRequest !== requestId) return;
      dashboard.value = response;
      if (card.value !== 'all' && !response.cards.some((item) => item.key === card.value)) card.value = 'all';
    } catch (caught) {
      if (currentRequest !== requestId) return;
      loadError.value = caught instanceof Error ? caught.message : 'Could not load dashboard filters';
    } finally {
      if (currentRequest === requestId) loading.value = false;
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
      await load();
    } catch (caught) {
      const message = caught instanceof Error ? caught.message : '';
      runtimeError.value = /different builds|database is unavailable|server is not ready/i.test(message)
        ? message
        : 'Could not connect to the compatible local ClearSpend server. Start or restart it from this branch, then try again.';
    } finally {
      runtimeChecking.value = false;
    }
  }

  function changeMonth(value: string): void {
    month.value = value;
    period.value = 'month';
  }

  function refresh(): void {
    revision.value += 1;
    void load();
  }

  watch([period, month, card], () => { if (runtimeReady.value) void load(); });
  onMounted(() => { void verifyRuntime(); });

  return {
    period,
    month,
    card,
    dashboard,
    loading,
    loadError,
    runtimeChecking,
    runtimeReady,
    runtimeError,
    revision,
    effectiveMonth,
    load,
    verifyRuntime,
    changeMonth,
    refresh,
  };
}
