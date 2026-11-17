<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref } from 'vue';
import { themes, type ThemeId } from './theme';

const props = defineProps<{ modelValue: ThemeId }>();
const emit = defineEmits<{ 'update:modelValue': [theme: ThemeId] }>();
const open = ref(false);
const wrap = ref<HTMLElement | null>(null);
const button = ref<HTMLButtonElement | null>(null);
const selected = computed(() => themes.find((theme) => theme.id === props.modelValue) ?? themes[0]);

function choose(theme: ThemeId): void {
  emit('update:modelValue', theme);
  open.value = false;
  void nextTick(() => button.value?.focus());
}

function handlePointerDown(event: PointerEvent): void {
  if (open.value && !wrap.value?.contains(event.target as Node)) open.value = false;
}

function handleKeydown(event: KeyboardEvent): void {
  if (event.key !== 'Escape' || !open.value) return;
  open.value = false;
  void nextTick(() => button.value?.focus());
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
  <div ref="wrap" class="theme-picker-wrap">
    <button ref="button" type="button" class="theme-picker-button" aria-label="Choose color theme" title="Choose color theme" :aria-expanded="open" aria-haspopup="menu" @click="open = !open">
      <span class="theme-picker-button-swatches" aria-hidden="true"><i v-for="color in selected.colors" :key="color" :style="{ background: color }" /></span>
      <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 3a9 9 0 1 0 0 18h1.4a2 2 0 0 0 1.7-3l-.4-.7a1.5 1.5 0 0 1 1.3-2.3h1a4 4 0 0 0 4-4c0-4.4-4-8-9-8Z"/><circle cx="7.5" cy="11" r="1"/><circle cx="10" cy="7.5" r="1"/><circle cx="15" cy="7.5" r="1"/></svg>
    </button>
    <section v-if="open" class="theme-picker-menu" role="menu" aria-label="Color themes">
      <header><strong>Dashboard colors</strong><small>Choose a palette for this browser</small></header>
      <div>
        <button v-for="theme in themes" :key="theme.id" type="button" role="menuitemradio" :aria-checked="theme.id === modelValue" :class="{ selected: theme.id === modelValue }" @click="choose(theme.id)">
          <span class="theme-option-swatches" aria-hidden="true"><i v-for="color in theme.colors" :key="color" :style="{ background: color }" /></span>
          <span><strong>{{ theme.name }}</strong><small>{{ theme.description }}</small></span>
          <b aria-hidden="true">{{ theme.id === modelValue ? '✓' : '' }}</b>
        </button>
      </div>
    </section>
  </div>
</template>
