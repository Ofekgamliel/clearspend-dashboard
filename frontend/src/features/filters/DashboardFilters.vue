<script setup lang="ts">
import type { DashboardCard, PeriodKey } from '../../api/contracts';
import { formatMonth } from '../../shared/format';
import { cardLabel, normalizeAvailableMonths } from './model';

const props = defineProps<{
  period: PeriodKey;
  month: string;
  card: string;
  cards: DashboardCard[];
  availableMonths: string[];
  loading: boolean;
  error: string;
}>();

const emit = defineEmits<{
  periodChange: [period: PeriodKey];
  monthChange: [month: string];
  cardChange: [card: string];
  retry: [];
}>();

function changeMonth(event: Event): void {
  emit('monthChange', (event.target as HTMLSelectElement).value);
}

function changeCard(event: Event): void {
  emit('cardChange', (event.target as HTMLSelectElement).value);
}
</script>

<template>
  <section class="dashboard-filters" aria-label="Dashboard filters" :aria-busy="loading">
    <div class="period-tabs" role="group" aria-label="Reporting period">
      <button type="button" :class="{ active: period === 'month' }" :aria-pressed="period === 'month'" @click="emit('periodChange', 'month')">Month</button>
      <button type="button" :class="{ active: period === 'year' }" :aria-pressed="period === 'year'" @click="emit('periodChange', 'year')">Latest year</button>
      <button type="button" :class="{ active: period === 'all' }" :aria-pressed="period === 'all'" @click="emit('periodChange', 'all')">All time</button>
    </div>

    <label class="filter-select month-filter">
      <span>Month</span>
      <select :value="month" :disabled="!availableMonths.length" @change="changeMonth">
        <option v-if="!availableMonths.length" value="">No months available</option>
        <option v-for="item in normalizeAvailableMonths(availableMonths)" :key="item" :value="item">{{ formatMonth(item) }}</option>
      </select>
    </label>

    <label class="filter-select card-filter">
      <span>Card</span>
      <select :value="card" @change="changeCard">
        <option value="all">All cards</option>
        <option v-for="item in cards" :key="item.key" :value="item.key">{{ cardLabel(item) }}</option>
      </select>
    </label>

    <div v-if="error" class="filter-error" role="alert">
      <span>{{ error }}</span>
      <button type="button" @click="emit('retry')">Retry</button>
    </div>
    <span v-else-if="loading" class="filter-loading" role="status">Updating…</span>
  </section>
</template>
