<script setup lang="ts">
import { computed } from 'vue';
import type { DashboardMetrics } from '../../api/contracts';
import { formatInteger, formatMoney } from '../../shared/format';
import { metricContext } from './model';

const props = defineProps<{
  metrics: DashboardMetrics;
  loading: boolean;
}>();

const context = computed(() => metricContext(props.metrics));
</script>

<template>
  <section class="metrics-grid" aria-label="Key metrics" :aria-busy="loading">
    <article class="metric-card hero-metric">
      <div class="metric-head"><span>Total spent</span><span class="metric-pill">Local data</span></div>
      <strong class="metric-value">{{ formatMoney(metrics.spent) }}</strong>
      <div class="mini-bars" aria-hidden="true"><i style="height:42%" /><i style="height:55%" /><i style="height:48%" /><i style="height:70%" /><i style="height:61%" /><i style="height:85%" /><i class="current" style="height:100%" /></div>
      <p>{{ context.transactionNote }}</p>
    </article>

    <article class="metric-card">
      <div class="metric-head"><span>Refunds &amp; credits</span><span class="metric-icon green" aria-hidden="true">↙</span></div>
      <strong class="metric-value">{{ formatMoney(metrics.refunds) }}</strong>
      <div class="metric-foot"><b>Credits</b><span>negative charges</span></div>
    </article>

    <article class="metric-card">
      <div class="metric-head"><span>Transactions</span><span class="metric-icon violet" aria-hidden="true">≈</span></div>
      <strong class="metric-value">{{ formatInteger(metrics.transactions) }}</strong>
      <div class="metric-foot"><b>Imported</b><span>{{ context.activeDaysNote }}</span></div>
    </article>

    <article class="metric-card">
      <div class="metric-head"><span>Daily average</span><span class="metric-icon amber" aria-hidden="true">⌁</span></div>
      <strong class="metric-value">{{ formatMoney(metrics.daily_average) }}</strong>
      <div class="metric-foot"><b>Active days</b><span>average spend</span></div>
    </article>
  </section>
</template>
