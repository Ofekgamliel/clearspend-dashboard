<script setup lang="ts">
import { computed, ref, watch } from 'vue';
import { getMerchantReference } from '../../api/merchants';
import { saveTransactionCategory } from '../../api/transactions';
import type { TransactionRow } from '../../api/contracts';
import { formatDate, formatSourceAmount } from '../../shared/format';
import { UiButton, UiDialog, UiField, UiSelect } from '../../shared/ui';

const props = defineProps<{ transaction: TransactionRow | null }>();
const emit = defineEmits<{
  close: [];
  saved: [message: { title: string; detail: string }];
}>();

const categories = ref<string[]>([]);
const selectedCategory = ref('');
const loading = ref(false);
const saving = ref(false);
const error = ref('');

const choices = computed(() => [...new Set([
  ...categories.value,
  props.transaction?.category ?? '',
])].filter(Boolean).sort((left, right) => left.localeCompare(right)));

function close(): void {
  if (!saving.value) emit('close');
}

async function loadCategories(): Promise<void> {
  if (categories.value.length) return;
  loading.value = true;
  try {
    categories.value = (await getMerchantReference()).categories;
  } catch (caught) {
    error.value = caught instanceof Error ? caught.message : 'Could not load category choices';
  } finally {
    loading.value = false;
  }
}

async function save(): Promise<void> {
  const item = props.transaction;
  const category = selectedCategory.value.trim();
  if (!item || !category) return;
  if (category === item.category && item.category_source !== 'transaction_override') {
    error.value = 'Choose a different category for this transaction.';
    return;
  }
  saving.value = true;
  error.value = '';
  try {
    const response = await saveTransactionCategory({ transaction_id: item.id, category, subcategory: '' });
    item.category = response.category;
    item.subcategory = response.subcategory;
    item.category_source = 'transaction_override';
    emit('saved', { title: 'Transaction corrected', detail: `${response.merchant_raw} · ${response.category}` });
  } catch (caught) {
    error.value = caught instanceof Error ? caught.message : 'Could not save category correction';
  } finally {
    saving.value = false;
  }
}

watch(() => props.transaction, (transaction) => {
  if (!transaction) return;
  selectedCategory.value = transaction.category;
  error.value = '';
  void loadCategories();
});
</script>

<template>
  <UiDialog :open="Boolean(transaction)" title-id="transaction-category-editor-title" close-label="Close category correction" size="medium" @request-close="close">
    <template #header><h2 id="transaction-category-editor-title">Change transaction category</h2><p>This correction applies only to this transaction.</p></template>
    <template v-if="transaction">
        <div class="transaction-editor-snapshot"><div><span>Merchant</span><strong>{{ transaction.merchant_display_name || transaction.merchant_raw }}</strong><small>{{ transaction.merchant_raw }}</small></div><div><span>Date</span><strong>{{ transaction.transaction_date ? formatDate(transaction.transaction_date) : '—' }}</strong></div><div><span>Card</span><strong>{{ transaction.provider.toUpperCase() }} •• {{ transaction.card_last4 }}</strong></div><div><span>Amount</span><strong>{{ formatSourceAmount(transaction.amount, transaction.charged_currency) }}</strong></div></div>
        <div class="transaction-category-choice"><div><span>Current category</span><strong>{{ transaction.category }}</strong></div><b aria-hidden="true">→</b><UiField for-id="transaction-category" label="New category"><UiSelect id="transaction-category" v-model="selectedCategory" :disabled="loading || saving"><option v-for="category in choices" :key="category" :value="category">{{ category }}</option></UiSelect></UiField></div>
        <p class="transaction-category-explanation"><b>i</b><span>The merchant rule remains “{{ transaction.merchant_category || transaction.category }}” for other transactions and future imports. The original imported row is preserved.</span></p>
        <p v-if="error" class="transaction-editor-error" role="alert">{{ error }}</p>
    </template>
    <template #footer><UiButton :disabled="saving" @click="close">Cancel</UiButton><UiButton variant="primary" :disabled="loading || !selectedCategory" :busy="saving" @click="save">{{ saving ? 'Saving…' : 'Save correction' }}</UiButton></template>
  </UiDialog>
</template>
