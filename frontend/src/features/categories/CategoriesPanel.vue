<script setup lang="ts">
import { computed, ref, watch } from 'vue';
import { getCategories } from '../../api/categories';
import type { CategoriesResponse, CategoryRow, EventScope, PeriodKey } from '../../api/contracts';
import { formatMoney, formatMonth, formatPercent } from '../../shared/format';
import { buildCategorySegments, categoryComparisonModel } from './model';

const scope = ref<EventScope>('all');
const props = defineProps<{
  period: PeriodKey;
  month: string;
  card: string;
}>();
const response = ref<CategoriesResponse | null>(null);
const loading = ref(true);
const error = ref('');
let requestId = 0;

const donut = computed(() => buildCategorySegments(response.value?.categories ?? []));

async function loadCategories(): Promise<void> {
  const currentRequest = ++requestId;
  loading.value = true;
  error.value = '';
  try {
    const payload = await getCategories({
      period: props.period,
      month: props.month,
      card: props.card,
      eventScope: scope.value,
    });
    if (currentRequest === requestId) response.value = payload;
  } catch (caught) {
    if (currentRequest !== requestId) return;
    error.value = caught instanceof Error ? caught.message : 'Could not load categories';
  } finally {
    if (currentRequest === requestId) loading.value = false;
  }
}

function comparisonFor(category: CategoryRow) {
  if (!response.value) return null;
  return categoryComparisonModel(category, response.value.category_comparison);
}

function comparisonTitle(category: CategoryRow): string {
  const comparison = comparisonFor(category);
  if (!comparison) return 'Previous-month comparison is unavailable';
  const previousMonth = formatMonth(comparison.previousMonth);
  if (comparison.status === 'new') return `No spending in ${previousMonth}`;
  if (comparison.status === 'unavailable') return `Comparison with ${previousMonth} is unavailable`;
  return `${formatMoney(category.previous_amount ?? 0)} in ${previousMonth}`;
}

watch(
  [scope, () => props.period, () => props.month, () => props.card],
  loadCategories,
  { immediate: true },
);
</script>

<template>
  <article class="categories-panel" aria-labelledby="categories-title">
    <header class="categories-head">
      <div>
        <p class="feature-kicker">First migrated feature</p>
        <h2 id="categories-title">Categories</h2>
        <p v-if="response" class="period-label">{{ response.period.label }}</p>
      </div>
      <div class="scope-toggle" role="group" aria-label="Category spending scope">
        <button type="button" :class="{ active: scope === 'all' }" :aria-pressed="scope === 'all'" @click="scope = 'all'">All spending</button>
        <button type="button" :class="{ active: scope === 'routine' }" :aria-pressed="scope === 'routine'" @click="scope = 'routine'">Routine only</button>
      </div>
    </header>

    <div v-if="loading && !response" class="panel-state" role="status">Loading categories…</div>
    <div v-else-if="error" class="panel-state error-state" role="alert">
      <span>{{ error }}</span>
      <button type="button" @click="loadCategories">Try again</button>
    </div>
    <div v-else-if="!response?.categories.length" class="panel-state">No category spending is available for this period.</div>
    <div v-else class="categories-body" :aria-busy="loading">
      <div class="category-donut" role="img" :aria-label="donut.ariaLabel" :style="{ background: donut.gradient }">
        <div class="donut-centre"><strong>{{ formatMoney(response.total) }}</strong><span>Total</span></div>
      </div>

      <div class="category-list" aria-label="Category spending breakdown">
        <div class="category-columns" aria-hidden="true"><span /><span>Category</span><span>Amount</span><span>Share</span><span>Vs prior</span></div>
        <div v-for="segment in donut.segments" :key="segment.category" class="category-row">
          <i class="category-dot" :style="{ background: segment.color }" />
          <span class="category-name">{{ segment.category }}</span>
          <strong>{{ formatMoney(segment.amount) }}</strong>
          <span class="category-share">{{ formatPercent(segment.share) }}</span>
          <span v-if="comparisonFor(segment)" class="comparison-badge" :class="comparisonFor(segment)?.status" :title="comparisonTitle(segment)">{{ comparisonFor(segment)?.label }}</span>
          <span v-else class="comparison-badge unavailable">—</span>
        </div>
      </div>
      <div v-if="loading" class="refresh-indicator" role="status">Updating…</div>
    </div>
  </article>
</template>
