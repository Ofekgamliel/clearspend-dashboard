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

const period = ref<PeriodKey>('month');
const month = ref('');
const card = ref('all');
const dashboard = ref<DashboardResponse | null>(null);
const filtersLoading = ref(true);
const filtersError = ref('');
function storedIncomeVisibility(): boolean {
  try { return localStorage.getItem('clearspend-income-hidden') === '1'; } catch { return false; }
}
const incomeHidden = ref(storedIncomeVisibility());
let requestId = 0;

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

watch([period, month, card], loadFilters, { immediate: true });
</script>

<template>
  <main class="preview-shell">
    <header class="preview-header">
      <div class="preview-brand"><div class="preview-mark" aria-hidden="true"><i /></div><strong>clear<span>spend</span></strong></div>
      <div class="preview-boundary"><b>Migration preview</b><span>Read-only · production remains in dist/</span></div>
    </header>
    <DashboardFilters
      :period="period"
      :month="effectiveMonth"
      :card="card"
      :cards="dashboard?.cards ?? []"
      :available-months="dashboard?.available_months ?? []"
      :loading="filtersLoading"
      :error="filtersError"
      @period-change="period = $event"
      @month-change="changeMonth"
      @card-change="card = $event"
      @retry="loadFilters"
    />
    <IncomePanel v-if="dashboard" :summary="dashboard.income_summary" :period="dashboard.period" :loading="filtersLoading" :hidden="incomeHidden" @privacy-change="changeIncomeVisibility" />
    <MetricsGrid v-if="dashboard" :metrics="dashboard.metrics" :loading="filtersLoading" />
    <TrendPanel v-if="dashboard" :dashboard="dashboard" :income-hidden="incomeHidden" :loading="filtersLoading" />
    <section class="preview-dashboard-grid">
      <CategoriesPanel :period="period" :month="month" :card="card" />
      <CardsPanel
        v-if="dashboard"
        :cards="dashboard.cards"
        :selected-card="card"
        :period-label="dashboard.period.label"
        :loading="filtersLoading"
        @card-change="card = $event"
      />
    </section>
    <RecurringPanel :period="period" :month="month" :card="card" />
    <EventsPanel :period="period" :month="month" :card="card" />
    <TransactionsPanel
      v-if="dashboard"
      :recent="dashboard.recent_transactions"
      :period="period"
      :month="month"
      :card="card"
      :period-label="dashboard.period.label"
      :loading="filtersLoading"
    />
  </main>
</template>
