<script setup lang="ts">
import { computed, ref, watch } from 'vue';
import { getDashboard } from './api/dashboard';
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

function openManagement(target: 'import' | 'audit' | 'merchants' | 'recurring'): void {
  manageMenuOpen.value = false;
  if (target === 'import') importManager.value?.open();
  else if (target === 'audit') importAudit.value?.open();
  else if (target === 'merchants') merchantManager.value?.open();
  else recurringPanel.value?.openManagement();
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
    title: `${payload.category} transactions`,
  });
}

function refreshData(): void {
  dataRevision.value += 1;
  void loadFilters();
}

watch([period, month, card], loadFilters, { immediate: true });
</script>

<template>
  <main class="preview-shell">
    <header class="preview-header">
      <div class="preview-brand"><div class="preview-mark" aria-hidden="true"><i /></div><strong>clear<span>spend</span></strong></div>
      <DashboardFilters
        :period="period" :month="effectiveMonth" :card="card" :cards="dashboard?.cards ?? []" :available-months="dashboard?.available_months ?? []"
        :loading="filtersLoading" :error="filtersError" @period-change="period = $event" @month-change="changeMonth" @card-change="card = $event" @retry="loadFilters"
      />
      <div class="preview-manage-wrap">
        <button type="button" class="preview-manage-button" :aria-expanded="manageMenuOpen" aria-haspopup="menu" @click="manageMenuOpen=!manageMenuOpen"><span aria-hidden="true">☷</span><strong>Manage data</strong></button>
        <div v-if="manageMenuOpen" class="preview-manage-menu" role="menu">
          <button type="button" role="menuitem" @click="openManagement('import')"><b>⇧</b><span><strong>Import statements</strong><small>Stage, review and reconcile files</small></span></button>
          <button type="button" role="menuitem" @click="openManagement('audit')"><b>≡</b><span><strong>Import history</strong><small>Coverage, inserted rows and duplicates</small></span></button>
          <button type="button" role="menuitem" @click="openManagement('merchants')"><b>◎</b><span><strong>Merchants</strong><small>Display names and permanent categories</small></span></button>
          <button type="button" role="menuitem" @click="openManagement('recurring')"><b>↻</b><span><strong>Recurring rules</strong><small>Membership, cadence and lifecycle</small></span></button>
        </div>
      </div>
    </header>
    <IncomePanel v-if="dashboard" ref="incomePanel" :summary="dashboard.income_summary" :period="dashboard.period" :loading="filtersLoading" :hidden="incomeHidden" @privacy-change="changeIncomeVisibility" />
    <MetricsGrid v-if="dashboard" :metrics="dashboard.metrics" :loading="filtersLoading" />
    <TrendPanel v-if="dashboard" :dashboard="dashboard" :income-hidden="incomeHidden" :loading="filtersLoading" />
    <section class="preview-dashboard-grid">
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
    <RecurringPanel ref="recurringPanel" :period="period" :month="month" :card="card" :refresh-key="dataRevision" @financial-data-change="refreshData" />
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
    <MerchantManagement ref="merchantManager" @financial-data-change="refreshData" />
    <ImportManager ref="importManager" @imported="refreshData" />
    <ImportAudit ref="importAudit" />
  </main>
</template>
