<script setup lang="ts">
import { computed, ref } from 'vue';
import CardsPanel from './features/cards/CardsPanel.vue';
import CategoriesPanel from './features/categories/CategoriesPanel.vue';
import { useDashboardData } from './features/dashboard/useDashboardData';
import EventsPanel from './features/events/EventsPanel.vue';
import DashboardFilters from './features/filters/DashboardFilters.vue';
import ImportAudit from './features/imports/ImportAudit.vue';
import ImportManager from './features/imports/ImportManager.vue';
import IncomePanel from './features/income/IncomePanel.vue';
import ManageDataMenu, { type ManagementTarget } from './features/management/ManageDataMenu.vue';
import MerchantManagement from './features/merchants/MerchantManagement.vue';
import MetricsGrid from './features/metrics/MetricsGrid.vue';
import ObservationsPanel from './features/observations/ObservationsPanel.vue';
import type { ObservationActivity } from './features/observations/model';
import RecurringPanel from './features/recurring/RecurringPanel.vue';
import TransactionsPanel from './features/transactions/TransactionsPanel.vue';
import TrendPanel from './features/trend/TrendPanel.vue';
import ThemePicker from './features/theme/ThemePicker.vue';
import { applyTheme, readStoredTheme, storeTheme, type ThemeId } from './features/theme/theme';

const {
  period,
  month,
  card,
  dashboard,
  loading: filtersLoading,
  loadError: filtersError,
  runtimeChecking,
  runtimeReady,
  runtimeError,
  revision: dataRevision,
  effectiveMonth,
  load: loadFilters,
  verifyRuntime,
  changeMonth,
  refresh: refreshData,
} = useDashboardData();

function storedIncomeVisibility(): boolean {
  try { return localStorage.getItem('clearspend-income-hidden') === '1'; } catch { return false; }
}

const incomeHidden = ref(storedIncomeVisibility());
const colorTheme = ref<ThemeId>(readStoredTheme());
applyTheme(colorTheme.value);
const incomePanel = ref<InstanceType<typeof IncomePanel> | null>(null);
const transactionsPanel = ref<InstanceType<typeof TransactionsPanel> | null>(null);
const recurringPanel = ref<InstanceType<typeof RecurringPanel> | null>(null);
const merchantManager = ref<InstanceType<typeof MerchantManagement> | null>(null);
const importManager = ref<InstanceType<typeof ImportManager> | null>(null);
const importAudit = ref<InstanceType<typeof ImportAudit> | null>(null);

const latestImportLabel = computed(() => {
  const latest = dashboard.value?.latest_import;
  if (!latest) return 'No statements imported yet';
  return `Last import: ${latest.original_name} · ${latest.status.replaceAll('_', ' ')}`;
});

function scrollToTop(): void {
  window.scrollTo({ top: 0, behavior: 'smooth' });
}

function openManagement(target: ManagementTarget | 'recurring', canonicalGroupId = ''): void {
  if (target === 'import') importManager.value?.open();
  else if (target === 'audit') importAudit.value?.open();
  else if (target === 'merchants') merchantManager.value?.open('all');
  else merchantManager.value?.open('all', { recurringFilter: 'all', selectGroup: canonicalGroupId });
}

function changeIncomeVisibility(hidden: boolean): void {
  incomeHidden.value = hidden;
  try { localStorage.setItem('clearspend-income-hidden', hidden ? '1' : '0'); } catch { /* Keep the in-memory preference. */ }
}

function changeColorTheme(theme: ThemeId): void {
  colorTheme.value = theme;
  applyTheme(theme);
  storeTheme(theme);
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
      <ThemePicker v-if="runtimeReady" :model-value="colorTheme" @update:model-value="changeColorTheme" />
      <ManageDataMenu v-if="runtimeReady" @select="openManagement" />
    </header>
    <section v-if="runtimeChecking" class="runtime-state" role="status"><strong>Connecting to ClearSpend…</strong><span>Checking the local server and database.</span></section>
    <section v-else-if="runtimeError" class="runtime-state error-state" role="alert"><strong>ClearSpend needs to reconnect</strong><span>{{ runtimeError }}</span><button type="button" @click="verifyRuntime">Try again</button></section>
    <template v-else>
      <IncomePanel v-if="dashboard" ref="incomePanel" :summary="dashboard.income_summary" :period="dashboard.period" :loading="filtersLoading" :hidden="incomeHidden" @privacy-change="changeIncomeVisibility" />
      <MetricsGrid v-if="dashboard" :metrics="dashboard.metrics" :loading="filtersLoading" />
      <section class="dashboard-analytics">
        <TrendPanel v-if="dashboard" :dashboard="dashboard" :income-hidden="incomeHidden" :loading="filtersLoading" />
        <CategoriesPanel :period="period" :month="month" :card="card" :refresh-key="dataRevision" @open-category="openCategoryTransactions" />
        <CardsPanel v-if="dashboard" :cards="dashboard.cards" :selected-card="card" :loading="filtersLoading" @card-change="card = $event" />
      </section>
      <ObservationsPanel :period="period" :month="month" :card="card" :income-hidden="incomeHidden" :refresh-key="dataRevision" @open-activity="openObservationActivity" />
      <RecurringPanel ref="recurringPanel" :period="period" :month="month" :card="card" :refresh-key="dataRevision" @financial-data-change="refreshData" @manage-recurring="openManagement('recurring', $event)" />
      <EventsPanel :period="period" :month="month" :card="card" :refresh-key="dataRevision" />
      <TransactionsPanel v-if="dashboard" ref="transactionsPanel" :recent="dashboard.recent_transactions" :period="period" :month="month" :card="card" :loading="filtersLoading" @financial-data-change="refreshData" />
      <footer class="app-footer"><span>{{ latestImportLabel }}</span><span><i aria-hidden="true" /> Local database connected</span></footer>
      <MerchantManagement ref="merchantManager" @financial-data-change="refreshData" />
      <ImportManager ref="importManager" @imported="refreshData" />
      <ImportAudit ref="importAudit" />
    </template>
  </main>
</template>
