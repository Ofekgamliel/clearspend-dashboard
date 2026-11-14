<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue';
import { getMerchantReference } from '../../api/merchants';
import { saveTransactionCategory } from '../../api/transactions';
import type { TransactionRow } from '../../api/contracts';
import { formatDate, formatSourceAmount } from '../../shared/format';
import { modalFocus as vModalFocus } from '../../shared/modalFocus';

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

function handleKeydown(event: KeyboardEvent): void {
  if (event.key === 'Escape' && props.transaction) close();
}

watch(() => props.transaction, (transaction) => {
  if (!transaction) return;
  selectedCategory.value = transaction.category;
  error.value = '';
  void loadCategories();
});
onMounted(() => document.addEventListener('keydown', handleKeydown));
onBeforeUnmount(() => document.removeEventListener('keydown', handleKeydown));
</script>

<template>
  <Teleport to="body">
    <div v-if="transaction" class="transaction-editor-backdrop" @mousedown.self="close">
      <section v-modal-focus class="transaction-category-editor" role="dialog" aria-modal="true" aria-labelledby="transaction-category-editor-title">
        <button type="button" class="transaction-editor-close" aria-label="Close category correction" @click="close">×</button>
        <header><h2 id="transaction-category-editor-title">Change transaction category</h2><p>This correction applies only to this transaction.</p></header>
        <div class="transaction-editor-snapshot"><div><span>Merchant</span><strong>{{ transaction.merchant_display_name || transaction.merchant_raw }}</strong><small>{{ transaction.merchant_raw }}</small></div><div><span>Date</span><strong>{{ transaction.transaction_date ? formatDate(transaction.transaction_date) : '—' }}</strong></div><div><span>Card</span><strong>{{ transaction.provider.toUpperCase() }} •• {{ transaction.card_last4 }}</strong></div><div><span>Amount</span><strong>{{ formatSourceAmount(transaction.amount, transaction.charged_currency) }}</strong></div></div>
        <div class="transaction-category-choice"><div><span>Current category</span><strong>{{ transaction.category }}</strong></div><b aria-hidden="true">→</b><label><span>New category</span><select v-model="selectedCategory" :disabled="loading || saving"><option v-for="category in choices" :key="category" :value="category">{{ category }}</option></select></label></div>
        <p class="transaction-category-explanation"><b>i</b><span>The merchant rule remains “{{ transaction.merchant_category || transaction.category }}” for other transactions and future imports. The original imported row is preserved.</span></p>
        <p v-if="error" class="transaction-editor-error" role="alert">{{ error }}</p>
        <footer><button type="button" class="secondary" :disabled="saving" @click="close">Cancel</button><button type="button" class="primary" :disabled="loading || saving || !selectedCategory" @click="save">{{ saving ? 'Saving…' : 'Save correction' }}</button></footer>
      </section>
    </div>
  </Teleport>
</template>
