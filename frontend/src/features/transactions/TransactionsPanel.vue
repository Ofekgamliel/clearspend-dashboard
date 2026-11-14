<script setup lang="ts">
import { ref } from 'vue';
import type { PeriodKey, RecentTransaction } from '../../api/contracts';
import { formatDate, formatMoney, formatMonth } from '../../shared/format';
import { reportingSourceLabel, type TransactionActivityOptions } from './model';
import TransactionBrowser from './TransactionBrowser.vue';

defineProps<{
  recent: RecentTransaction[];
  period: PeriodKey;
  month: string;
  card: string;
  periodLabel: string;
  loading: boolean;
}>();
const emit = defineEmits<{ financialDataChange: [] }>();
const browser = ref<InstanceType<typeof TransactionBrowser> | null>(null);

function reportingLabel(row: RecentTransaction): string {
  if (row.billing_date) return formatDate(row.billing_date);
  if (row.billing_month) return formatMonth(row.billing_month);
  return row.transaction_date ? formatDate(row.transaction_date) : '—';
}

function openActivity(options: TransactionActivityOptions): void {
  browser.value?.openActivity(options);
}

defineExpose({ openActivity });
</script>

<template>
  <article class="transactions-panel" aria-labelledby="transactions-title" :aria-busy="loading">
    <header class="transactions-head">
      <div><h2 id="transactions-title">Recent transactions</h2><p>Five-column summary · open all transactions for full source details</p></div>
      <button type="button" class="transactions-view-all" @click="browser?.open()">View all transactions →</button>
    </header>
    <div class="recent-table-wrap">
      <table class="recent-transactions-table">
        <thead><tr><th>Merchant</th><th>Category</th><th>Card</th><th>Reporting period</th><th class="right">Amount</th></tr></thead>
        <tbody>
          <tr v-for="(item, index) in recent" :key="`${item.provider}-${item.card_last4}-${item.transaction_date}-${index}`">
            <td><span class="recent-merchant-icon" :class="{ refund: item.amount < 0 }">{{ item.merchant_raw.trim().charAt(0).toUpperCase() || '?' }}</span><span><strong dir="auto">{{ item.merchant_raw }}</strong><small>{{ item.provider.toUpperCase() }} statement</small></span></td>
            <td><span dir="auto" class="transaction-category-pill" :class="{ review: item.category === 'Needs review' }">{{ item.category }}</span><small v-if="item.subcategory" dir="auto">{{ item.subcategory }}</small></td>
            <td><strong><span class="recent-card-mark" :class="{ max: item.provider === 'max' }">{{ item.provider === 'max' ? 'M' : 'I' }}</span>•• {{ item.card_last4 }}</strong></td>
            <td><strong>{{ reportingLabel(item) }}</strong><small>{{ reportingSourceLabel(item.billing_month_source) }}</small></td>
            <td dir="ltr" class="right" :class="{ charge: item.amount >= 0, refund: item.amount < 0 }">{{ item.amount < 0 ? '+' : '−' }}{{ formatMoney(Math.abs(item.amount)) }}</td>
          </tr>
          <tr v-if="!recent.length"><td colspan="5" class="transactions-empty">No transactions found.</td></tr>
        </tbody>
      </table>
    </div>
  </article>
  <TransactionBrowser
    ref="browser"
    :period="period"
    :month="month"
    :card="card"
    :period-label="periodLabel"
    @financial-data-change="emit('financialDataChange')"
  />
</template>
