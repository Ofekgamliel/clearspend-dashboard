<script setup lang="ts">
import type { DashboardCard } from '../../api/contracts';
import { formatMoney, formatPercent } from '../../shared/format';
import { UiSkeleton } from '../../shared/ui';
import { cardProviderClass, cardShareWidth, cardTransactionLabel } from './model';

defineProps<{
  cards: DashboardCard[] | null;
  selectedCard: string;
  loading: boolean;
}>();

const emit = defineEmits<{
  cardChange: [card: string];
}>();
</script>

<template>
  <article class="cards-panel" aria-labelledby="cards-title" :aria-busy="loading">
    <header class="cards-head">
      <div><h2 id="cards-title">Spending by card</h2></div>
    </header>
    <div v-if="loading && !cards" class="cards-list cards-skeleton" aria-hidden="true">
      <div v-for="index in 3" :key="index" class="payment-card"><UiSkeleton class="card-logo-skeleton" shape="block" /><span><UiSkeleton shape="line" /><UiSkeleton shape="line" /></span><span><UiSkeleton shape="line" /><UiSkeleton shape="line" /></span><UiSkeleton class="card-bar-skeleton" shape="line" /></div>
    </div>
    <div v-else-if="cards?.length" class="cards-list">
      <button
        v-for="item in cards"
        :key="item.key"
        type="button"
        class="payment-card"
        :class="{ selected: selectedCard === item.key }"
        :aria-pressed="selectedCard === item.key"
        @click="emit('cardChange', item.key)"
      >
        <span class="payment-logo" :class="cardProviderClass(item)" aria-hidden="true">
          <template v-if="cardProviderClass(item) === 'mastercard'"><i /><b /></template>
          <template v-else>MC</template>
        </span>
        <span class="payment-info"><strong>{{ item.product_name }}</strong><small>•••• {{ item.card_last4 }} · {{ item.provider.toUpperCase() }}</small></span>
        <span class="payment-total"><strong>{{ formatMoney(item.amount) }}</strong><small>{{ formatPercent(item.share) }} · {{ cardTransactionLabel(item.transactions) }}</small></span>
        <span class="payment-bar" aria-hidden="true"><i :style="{ width: `${cardShareWidth(item.share)}%` }" /></span>
      </button>
    </div>
    <p v-else-if="cards" class="cards-empty">No transactions in this period.</p>
    <p v-else class="cards-empty dashboard-panel-error">Dashboard card data is unavailable.</p>
  </article>
</template>
