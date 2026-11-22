<script setup lang="ts">
import { computed, ref } from 'vue';
import type { IncomeSummary, ReportingPeriod } from '../../api/contracts';
import { formatMoney } from '../../shared/format';
import { UiSkeleton } from '../../shared/ui';
import { averageRangeLabel, incomeAllocation, incomePeriodLabel } from './model';

const props = defineProps<{
  summary: IncomeSummary | null;
  period: ReportingPeriod | null;
  loading: boolean;
  hidden: boolean;
}>();
const emit = defineEmits<{ privacyChange: [hidden: boolean] }>();
const allocation = computed(() => props.summary ? incomeAllocation(props.summary) : null);
const panelElement = ref<HTMLElement | null>(null);

function togglePrivacy(): void {
  emit('privacyChange', !props.hidden);
}
function focusPanel(): void { panelElement.value?.scrollIntoView({ behavior: 'smooth', block: 'start' }); }
defineExpose({ focusPanel });
</script>

<template>
  <section ref="panelElement" class="income-panel" :class="{ 'income-private': hidden }" aria-label="Income and spending" :aria-busy="loading">
    <div class="income-head">
      <div>
        <h2>Income &amp; spending</h2>
        <p v-if="period && summary">{{ incomePeriodLabel(period, summary) }}</p>
        <UiSkeleton v-else-if="loading" class="income-heading-skeleton" shape="line" />
      </div>
      <button
        class="income-privacy-button"
        type="button"
        :aria-label="hidden ? 'Show income values' : 'Hide income values'"
        :title="hidden ? 'Show income values' : 'Hide income values'"
        :aria-pressed="hidden"
        @click="togglePrivacy"
      >
        <svg v-if="!hidden" viewBox="0 0 24 24" aria-hidden="true"><path d="M2.5 12s3.5-6 9.5-6 9.5 6 9.5 6-3.5 6-9.5 6-9.5-6-9.5-6Z"/><circle cx="12" cy="12" r="2.7"/></svg>
        <svg v-else viewBox="0 0 24 24" aria-hidden="true"><path d="m3 3 18 18M10.6 6.1A10.7 10.7 0 0 1 12 6c6 0 9.5 6 9.5 6a15 15 0 0 1-2.6 3.2M6.6 6.7C4 8.4 2.5 12 2.5 12s3.5 6 9.5 6c1 0 2-.2 2.9-.5"/></svg>
      </button>
    </div>

    <div v-if="loading && (!summary || !period)" class="income-skeleton" aria-hidden="true">
      <div class="income-skeleton-metrics"><div v-for="index in 3" :key="index"><UiSkeleton shape="line" /><UiSkeleton shape="line" /><UiSkeleton v-if="index === 3" shape="line" /></div></div>
      <UiSkeleton class="income-skeleton-allocation" />
      <div class="income-skeleton-averages"><div v-for="index in 3" :key="index"><UiSkeleton shape="line" /><UiSkeleton shape="line" /><UiSkeleton shape="line" /></div></div>
    </div>

    <div v-else-if="!summary || !period" class="dashboard-panel-error">Dashboard data is unavailable.</div>

    <div v-else-if="!hidden" class="income-metrics">
      <div><span>Income</span><strong>{{ summary.has_income ? formatMoney(summary.income) : 'No income data' }}</strong></div>
      <div><span>Net spending</span><strong>{{ formatMoney(summary.spending) }}</strong></div>
      <div class="income-remaining" :class="{ over: summary.has_income && summary.remaining < 0 }">
        <span>Amount left</span>
        <strong>{{ summary.has_income ? formatMoney(summary.remaining) : '—' }}</strong>
        <small>{{ summary.has_income ? `${summary.remaining_percentage}% of income left` : 'Import an income XLSX to calculate the balance' }}</small>
      </div>
    </div>

    <div v-if="summary && period && !hidden" class="income-allocation" aria-label="Income allocation">
      <span class="income-spent-segment" :class="{ over: allocation?.over, unavailable: allocation?.unavailable }" :style="{ width: `${allocation?.spentWidth ?? 0}%` }"><b>{{ allocation?.spentLabel }}</b></span>
      <span class="income-left-segment" :style="{ width: `${allocation?.leftWidth ?? 0}%` }"><b>{{ allocation?.leftLabel }}</b></span>
    </div>

    <div v-if="summary && period && !hidden" class="income-averages">
      <div class="income-average-title"><strong>Monthly averages</strong><small>{{ averageRangeLabel(summary) }}</small></div>
      <div><span>Average spending</span><strong>{{ summary.averages.spending_months ? formatMoney(summary.averages.spending) : '—' }}</strong><small>{{ summary.averages.spending_months ? `${summary.averages.spending_months} spending months · all cards` : 'No spending months' }}</small></div>
      <div class="average-left" :class="{ negative: summary.averages.amount_left_months && summary.averages.amount_left < 0 }"><span>Average amount left</span><strong>{{ summary.averages.amount_left_months ? formatMoney(summary.averages.amount_left) : '—' }}</strong><small>{{ summary.averages.amount_left_months ? `${summary.averages.amount_left_months} months with income` : 'No months with income' }}</small></div>
    </div>

    <div v-if="summary && period && hidden" class="income-hidden-state" role="status" aria-label="Income and spending values are hidden">
      <div class="income-metrics" aria-hidden="true">
        <div><span>Income</span><strong>••••••</strong></div>
        <div><span>Net spending</span><strong>••••••</strong></div>
        <div><span>Amount left</span><strong>••••••</strong><small>Values hidden</small></div>
      </div>
      <div class="income-allocation income-hidden-allocation" aria-hidden="true"><span /><span /></div>
      <div class="income-averages" aria-hidden="true">
        <div class="income-average-title"><strong>Monthly averages</strong><small>Values hidden</small></div>
        <div><span>Average spending</span><strong>••••••</strong><small>Hidden</small></div>
        <div><span>Average amount left</span><strong>••••••</strong><small>Hidden</small></div>
      </div>
    </div>
  </section>
</template>
