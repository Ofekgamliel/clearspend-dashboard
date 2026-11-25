<script setup lang="ts">
import { computed, ref, watch } from 'vue';
import type { RecurringUpcomingPayment, RecurringUpcomingResponse, RecurringUnresolvedReason } from '../../api/contracts';
import { formatDate, formatMoney, formatMonth } from '../../shared/format';

const props = defineProps<{ data: RecurringUpcomingResponse }>();
const selectedMonth = ref(props.data.anchor_month);

watch(() => props.data.anchor_month, (month) => { selectedMonth.value = month; });

const selected = computed(() => (
  props.data.months.find((item) => item.month === selectedMonth.value) ?? props.data.months[0]
));

const unresolvedLabels: Record<RecurringUnresolvedReason, string> = {
  unsupported_cadence: 'Schedule not supported',
  insufficient_schedule_history: 'Not enough history',
  ambiguous_phase: 'Schedule unclear',
  unknown_lifecycle: 'Lifecycle unclear',
  ambiguous_card: 'Card could not be determined',
  invalid_installment_evidence: 'Installment details unclear',
};

function dateLabel(payment: RecurringUpcomingPayment, month: string): string {
  if (!payment.expected_date) return `Expected in ${formatMonth(month)}`;
  if (payment.date_evidence === 'estimated') return `Around ${formatDate(payment.expected_date)} · estimated`;
  return formatDate(payment.expected_date);
}

function evidenceLabel(payment: RecurringUpcomingPayment): string {
  if (payment.amount_evidence === 'unknown') return 'Unknown amount';
  if (payment.amount_confidence === 'provisional') return 'Based on first payment';
  if (payment.amount_confidence === 'developing') return 'Estimate · developing';
  if (payment.amount_evidence === 'estimate') return 'Estimate';
  if (payment.occurrence_status === 'unexpected_card') return 'Confirmed · different card';
  if (payment.occurrence_status === 'unexpected_actual') return 'Confirmed · not forecast';
  return 'Confirmed';
}

function monthComparison(value: string | null): string {
  return value === 'highest_expected'
    ? 'Highest expected'
    : value === 'highest_known_estimate' ? 'Highest known estimate' : '';
}
</script>

<template>
  <section class="recurring-upcoming" aria-labelledby="recurring-upcoming-heading">
    <h3 id="recurring-upcoming-heading" class="visually-hidden">Upcoming recurring payments</h3>
    <div class="recurring-upcoming-months">
      <button
        v-for="month in data.months"
        :key="month.month"
        type="button"
        :class="{ selected: selected?.month === month.month }"
        :aria-pressed="selected?.month === month.month"
        @click="selectedMonth = month.month"
      >
        <span class="recurring-month-primary">
          <span>{{ formatMonth(month.month) }}</span>
          <strong>{{ formatMoney(month.comparable_total) }}</strong>
          <small class="known-label">Known expected</small>
        </span>
        <span class="recurring-month-secondary">
          <small>{{ month.payment_count }} {{ month.payment_count === 1 ? 'payment' : 'payments' }}</small>
          <small v-if="month.unknown_amount_count">{{ month.unknown_amount_count }} unknown</small>
          <i v-if="monthComparison(month.comparison_label)">{{ monthComparison(month.comparison_label) }}</i>
          <em v-if="month.annual_count || month.ending_installment_count">
            <template v-if="month.annual_count">Annual {{ month.annual_count }}</template><template v-if="month.annual_count && month.ending_installment_count"> · </template><template v-if="month.ending_installment_count">Ending {{ month.ending_installment_count }}</template>
          </em>
        </span>
      </button>
    </div>

    <div v-if="selected" class="recurring-upcoming-detail">
      <div v-if="selected.payments.length" class="recurring-upcoming-payments" role="table" :aria-label="`${formatMonth(selected.month)} expected payments`">
        <div class="recurring-upcoming-columns" role="row"><span role="columnheader">Expected date</span><span role="columnheader">Payment</span><span role="columnheader">Type / evidence</span><span role="columnheader">Expected amount</span></div>
        <div class="recurring-upcoming-payment-list" role="region" tabindex="0" :aria-label="`${formatMonth(selected.month)} expected payments`">
          <div role="rowgroup">
            <article v-for="payment in selected.payments" :key="payment.occurrence_id" role="row">
              <time role="cell">{{ dateLabel(payment, selected.month) }}</time>
              <div class="recurring-upcoming-payment-name" role="cell"><strong dir="auto">{{ payment.display_name }}</strong><small>{{ payment.card.provider.toUpperCase() }} •• {{ payment.card.last4 }}<template v-if="payment.installment_number"> · {{ payment.installment_number }}/{{ payment.installment_total }}</template></small><span><i v-if="payment.annual">Annual</i><i v-if="payment.ending">Final installment</i></span></div>
              <div class="recurring-upcoming-evidence" role="cell"><strong>{{ payment.payment_type }}</strong><small>{{ evidenceLabel(payment) }}</small><small v-if="payment.recent_range">Recent range {{ formatMoney(payment.recent_range[0]) }}–{{ formatMoney(payment.recent_range[1]) }}</small></div>
              <div class="recurring-upcoming-amount" role="cell"><strong>{{ payment.amount === null ? '—' : formatMoney(payment.amount) }}</strong></div>
            </article>
          </div>
        </div>
      </div>
      <p v-else class="recurring-upcoming-empty">No expected payments.</p>
    </div>

    <details v-if="data.unresolved.length" class="recurring-unresolved">
      <summary>Not forecast · {{ data.unresolved.length }}</summary>
      <div class="recurring-unresolved-list" role="region" tabindex="0" aria-label="Sources not forecast"><ul><li v-for="item in data.unresolved" :key="`${item.source_kind}:${item.source_id}`"><strong dir="auto">{{ item.display_name }}</strong><span>{{ unresolvedLabels[item.reason] }}</span></li></ul></div>
    </details>
    <p class="visually-hidden" role="status" aria-live="polite">Three-month recurring forecast loaded.</p>
  </section>
</template>
