<script setup lang="ts">
import { nextTick, onBeforeUnmount, onMounted, ref } from 'vue';
import type { DashboardCard } from '../../api/contracts';
import { formatMoney, formatPercent } from '../../shared/format';
import { cardProviderClass, cardShareWidth, cardTransactionLabel } from './model';

defineProps<{
  cards: DashboardCard[];
  selectedCard: string;
  periodLabel: string;
  loading: boolean;
}>();

const emit = defineEmits<{
  cardChange: [card: string];
}>();

const helpOpen = ref(false);
const helpWrap = ref<HTMLElement | null>(null);
const helpButton = ref<HTMLButtonElement | null>(null);

function closeHelp(restoreFocus = false): void {
  helpOpen.value = false;
  if (restoreFocus) void nextTick(() => helpButton.value?.focus());
}

function handlePointerDown(event: PointerEvent): void {
  if (helpOpen.value && !helpWrap.value?.contains(event.target as Node)) closeHelp();
}

function handleKeydown(event: KeyboardEvent): void {
  if (event.key === 'Escape' && helpOpen.value) closeHelp(true);
}

onMounted(() => {
  document.addEventListener('pointerdown', handlePointerDown);
  document.addEventListener('keydown', handleKeydown);
});
onBeforeUnmount(() => {
  document.removeEventListener('pointerdown', handlePointerDown);
  document.removeEventListener('keydown', handleKeydown);
});
</script>

<template>
  <article class="cards-panel" aria-labelledby="cards-title" :aria-busy="loading">
    <header class="cards-head">
      <div><h2 id="cards-title">Spending by card</h2><p>{{ periodLabel }}</p></div>
      <div ref="helpWrap" class="cards-help-wrap">
        <button ref="helpButton" type="button" class="cards-help-button" aria-label="Card filtering help" aria-haspopup="true" :aria-expanded="helpOpen" @click="helpOpen = !helpOpen">•••</button>
        <div v-if="helpOpen" class="cards-help-popover" role="status"><strong>Card filtering</strong><span>Select a card to filter every metric, chart, and detail view.</span></div>
      </div>
    </header>
    <div v-if="cards.length" class="cards-list">
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
    <p v-else class="cards-empty">No transactions in this period.</p>
  </article>
</template>
