<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue';
import { getDashboard } from './api/dashboard';
import { getRuntimeHealth, runtimeCompatibilityError } from './api/runtime.ts';
import type { DashboardResponse, PeriodKey } from './api/contracts';
import CategoriesPanel from './features/categories/CategoriesPanel.vue';
import CardsPanel from './features/cards/CardsPanel.vue';
import DashboardFilters from './features/filters/DashboardFilters.vue';
import { selectedMonth } from './features/filters/model';
import IncomePanel from './features/income/IncomePanel.vue';
import MetricsGrid from './features/metrics/MetricsGrid.vue';
import TrendPanel from './features/trend/TrendPanel.vue';
import TransactionsPanel from './features/transactions/TransactionsPanel.vue';
import RecurringPanel from './features/recurring/RecurringPanel.vue';
import EventsPanel from './features/events/EventsPanel.vue';
import ObservationsPanel from './features/observations/ObservationsPanel.vue';
import MerchantManagement from './features/merchants/MerchantManagement.vue';
import ImportManager from './features/imports/ImportManager.vue';
import ImportAudit from './features/imports/ImportAudit.vue';
import type { ObservationActivity } from './features/observations/model';

const period = ref<PeriodKey>('month');
const month = ref('');
const card = ref('all');
const dashboard = ref<DashboardResponse | null>(null);
const filtersLoading = ref(true);
const filtersError = ref('');
const runtimeChecking = ref(true);
const runtimeReady = ref(false);
const runtimeError = ref('');
const dataRevision = ref(0);
function storedIncomeVisibility(): boolean {
  try { return localStorage.getItem('clearspend-income-hidden') === '1'; } catch { return false; }
}
const incomeHidden = ref(storedIncomeVisibility());
let requestId = 0;
const incomePanel = ref<InstanceType<typeof IncomePanel> | null>(null);
const transactionsPanel = ref<InstanceType<typeof TransactionsPanel> | null>(null);
const recurringPanel = ref<InstanceType<typeof RecurringPanel> | null>(null);
const eventsPanel = ref<InstanceType<typeof EventsPanel> | null>(null);
const merchantManager = ref<InstanceType<typeof MerchantManagement> | null>(null);
const importManager = ref<InstanceType<typeof ImportManager> | null>(null);
const importAudit = ref<InstanceType<typeof ImportAudit> | null>(null);
const manageMenuOpen = ref(false);
const appManageWrap = ref<HTMLElement | null>(null);
const appManageButton = ref<HTMLButtonElement | null>(null);

const latestImportLabel = computed(() => {
  const latest = dashboard.value?.latest_import;
  if (!latest) return 'No statements imported yet';
  return `Last import: ${latest.original_name} · ${latest.status.replaceAll('_', ' ')}`;
});

function scrollToTop(): void {
  window.scrollTo({ top: 0, behavior: 'smooth' });
}

function openManagement(target: 'import' | 'audit' | 'merchants' | 'needs_review' | 'recurring', canonicalGroupId = ''): void {
  manageMenuOpen.value = false;
  if (target === 'import') importManager.value?.open();
  else if (target === 'audit') importAudit.value?.open();
  else if (target === 'merchants') merchantManager.value?.open('all');
  else if (target === 'needs_review') merchantManager.value?.open('needs_review');
  else merchantManager.value?.open('all', { recurringFilter: 'all', selectGroup: canonicalGroupId });
}

function handleManagePointerDown(event: PointerEvent): void {
  if (manageMenuOpen.value && !appManageWrap.value?.contains(event.target as Node)) manageMenuOpen.value = false;
}

function handleManageKeydown(event: KeyboardEvent): void {
  if (event.key !== 'Escape' || !manageMenuOpen.value) return;
  manageMenuOpen.value = false;
  void nextTick(() => appManageButton.value?.focus());
}

const effectiveMonth = computed(() => selectedMonth(
  month.value,
  dashboard.value?.period.start ?? null,
  dashboard.value?.available_months ?? [],
));

async function loadFilters(): Promise<void> {
  const currentRequest = ++requestId;
  filtersLoading.value = true;
  filtersError.value = '';
  try {
    const response = await getDashboard({
      period: period.value,
      month: month.value,
      card: card.value,
    });
    if (currentRequest !== requestId) return;
    dashboard.value = response;
    if (card.value !== 'all' && !response.cards.some((item) => item.key === card.value)) {
      card.value = 'all';
    }
  } catch (caught) {
    if (currentRequest !== requestId) return;
    filtersError.value = caught instanceof Error ? caught.message : 'Could not load dashboard filters';
  } finally {
    if (currentRequest === requestId) filtersLoading.value = false;
  }
}

async function verifyRuntime(): Promise<void> {
  runtimeChecking.value = true;
  runtimeReady.value = false;
  runtimeError.value = '';
  try {
    const health = await getRuntimeHealth();
    const compatibilityError = runtimeCompatibilityError(health);
    if (compatibilityError) throw new Error(compatibilityError);
    runtimeReady.value = true;
    await loadFilters();
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

function changeIncomeVisibility(hidden: boolean): void {
  incomeHidden.value = hidden;
  try { localStorage.setItem('clearspend-income-hidden', hidden ? '1' : '0'); } catch { /* Keep the in-memory preference. */ }
}

function openObservationActivity(activity: ObservationActivity): void {
  if (activity.target === 'income') {
    incomePanel.value?.focusPanel();
    return;
  }
  if (activity.target === 'recurring') {
    recurringPanel.value?.openActivity(activity.recurringTab ?? 'series', activity.recurringSeriesId ?? '');
    return;
  }
  transactionsPanel.value?.openActivity({
    transactionIds: activity.transactionIds,
    search: activity.search,
    category: activity.category,
    routine: activity.routine,
    title: activity.label,
  });
}

function openCategoryTransactions(payload: { category: string; routine: boolean }): void {
  transactionsPanel.value?.openActivity({
    category: payload.category,
    routine: payload.routine,
    grouped: true,
    title: payload.category,
  });
}

function refreshData(): void {
  dataRevision.value += 1;
  void loadFilters();
}

watch([period, month, card], () => { if (runtimeReady.value) void loadFilters(); });
onMounted(() => {
  document.addEventListener('pointerdown', handleManagePointerDown);
  document.addEventListener('keydown', handleManageKeydown);
  void verifyRuntime();
});
onBeforeUnmount(() => {
  document.removeEventListener('pointerdown', handleManagePointerDown);
  document.removeEventListener('keydown', handleManageKeydown);
});
</script>

<template>
  <main class="app-shell">
    <header class="app-header">
      <a class="app-brand" href="#" aria-label="ClearSpend home" @click.prevent="scrollToTop"><span class="app-brand-mark" aria-hidden="true"><i /></span><strong>clear<span>spend</span></strong></a>
      <span class="app-header-divider" aria-hidden="true" />
      <DashboardFilters v-if="runtimeReady"
        :period="period" :month="effectiveMonth" :card="card" :cards="dashboard?.cards ?? []" :available-months="dashboard?.available_months ?? []"
        :loading="filtersLoading" :error="filtersError" @period-change="period = $event" @month-change="changeMonth" @card-change="card = $event" @retry="loadFilters"
      />
      <div v-if="runtimeReady" ref="appManageWrap" class="app-manage-wrap">
        <button ref="appManageButton" type="button" class="app-manage-button" aria-label="Manage data" title="Manage data" :aria-expanded="manageMenuOpen" aria-haspopup="menu" @click="manageMenuOpen=!manageMenuOpen"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M4 7h10M18 7h2M4 17h2M10 17h10M14 4v6M6 14v6"/><circle cx="14" cy="7" r="2.5"/><circle cx="8" cy="17" r="2.5"/></svg></button>
        <div v-if="manageMenuOpen" class="app-manage-menu" role="menu">
          <button type="button" role="menuitem" @click="openManagement('import')"><b>⇧</b><span><strong>Import statements</strong><small>Stage, review and reconcile files</small></span></button>
          <button type="button" role="menuitem" @click="openManagement('audit')"><b>≡</b><span><strong>Import history</strong><small>Coverage, inserted rows and duplicates</small></span></button>
          <button type="button" role="menuitem" @click="openManagement('merchants')"><b>◎</b><span><strong>Merchants</strong><small>Display names and permanent categories</small></span></button>
        </div>
      </div>
    </header>
    <section v-if="runtimeChecking" class="runtime-state" role="status"><strong>Connecting to ClearSpend…</strong><span>Checking the local server and database.</span></section>
    <section v-else-if="runtimeError" class="runtime-state error-state" role="alert"><strong>ClearSpend needs to reconnect</strong><span>{{ runtimeError }}</span><button type="button" @click="verifyRuntime">Try again</button></section>
    <template v-else>
    <IncomePanel v-if="dashboard" ref="incomePanel" :summary="dashboard.income_summary" :period="dashboard.period" :loading="filtersLoading" :hidden="incomeHidden" @privacy-change="changeIncomeVisibility" />
    <MetricsGrid v-if="dashboard" :metrics="dashboard.metrics" :loading="filtersLoading" />
    <section class="dashboard-analytics">
      <TrendPanel v-if="dashboard" :dashboard="dashboard" :income-hidden="incomeHidden" :loading="filtersLoading" />
      <CategoriesPanel :period="period" :month="month" :card="card" :refresh-key="dataRevision" @open-category="openCategoryTransactions" />
      <CardsPanel
        v-if="dashboard"
        :cards="dashboard.cards"
        :selected-card="card"
        :period-label="dashboard.period.label"
        :loading="filtersLoading"
        @card-change="card = $event"
      />
    </section>
    <ObservationsPanel :period="period" :month="month" :card="card" :income-hidden="incomeHidden" :refresh-key="dataRevision" @open-activity="openObservationActivity" />
    <RecurringPanel ref="recurringPanel" :period="period" :month="month" :card="card" :refresh-key="dataRevision" @financial-data-change="refreshData" @manage-recurring="openManagement('recurring', $event)" />
    <EventsPanel ref="eventsPanel" :period="period" :month="month" :card="card" :refresh-key="dataRevision" />
    <TransactionsPanel
      v-if="dashboard"
      ref="transactionsPanel"
      :recent="dashboard.recent_transactions"
      :period="period"
      :month="month"
      :card="card"
      :period-label="dashboard.period.label"
      :loading="filtersLoading"
      @financial-data-change="refreshData"
    />
    <footer class="app-footer"><span>{{ latestImportLabel }}</span><span><i aria-hidden="true" /> Local database connected</span></footer>
    <MerchantManagement ref="merchantManager" @financial-data-change="refreshData" />
    <ImportManager ref="importManager" @imported="refreshData" />
    <ImportAudit ref="importAudit" />
    </template>
  </main>
</template>
