<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref } from 'vue';
import { themes, type ThemeId } from './theme';

const props = defineProps<{ modelValue: ThemeId }>();
const emit = defineEmits<{ 'update:modelValue': [theme: ThemeId] }>();
const open = ref(false);
const wrap = ref<HTMLElement | null>(null);
const trigger = ref<HTMLButtonElement | null>(null);
const options = ref<HTMLButtonElement[]>([]);
const selected = computed(() => themes.find((theme) => theme.id === props.modelValue) ?? themes[0]);

function setOption(element: Element | null, index: number): void {
  if (element instanceof HTMLButtonElement) options.value[index] = element;
}

function focusOption(index: number): void {
  const bounded = (index + themes.length) % themes.length;
  options.value[bounded]?.focus();
}

async function showMenu(focusSelected = false): Promise<void> {
  open.value = true;
  await nextTick();
  if (focusSelected) focusOption(themes.findIndex((theme) => theme.id === props.modelValue));
}

function closeMenu(restoreFocus = false): void {
  open.value = false;
  if (restoreFocus) void nextTick(() => trigger.value?.focus());
}

function choose(theme: ThemeId): void {
  emit('update:modelValue', theme);
  closeMenu(true);
}

function handleTriggerKeydown(event: KeyboardEvent): void {
  if (!['ArrowDown', 'ArrowUp'].includes(event.key)) return;
  event.preventDefault();
  void showMenu(true);
}

function handleMenuKeydown(event: KeyboardEvent): void {
  const activeIndex = options.value.findIndex((option) => option === document.activeElement);
  if (event.key === 'Escape') { event.preventDefault(); closeMenu(true); }
  else if (event.key === 'ArrowDown') { event.preventDefault(); focusOption(activeIndex + 1); }
  else if (event.key === 'ArrowUp') { event.preventDefault(); focusOption(activeIndex - 1); }
  else if (event.key === 'Home') { event.preventDefault(); focusOption(0); }
  else if (event.key === 'End') { event.preventDefault(); focusOption(themes.length - 1); }
  else if (event.key === 'Tab') closeMenu();
}

function handlePointerDown(event: PointerEvent): void {
  if (open.value && !wrap.value?.contains(event.target as Node)) closeMenu();
}

onMounted(() => document.addEventListener('pointerdown', handlePointerDown));
onBeforeUnmount(() => document.removeEventListener('pointerdown', handlePointerDown));
</script>

<template>
  <div ref="wrap" class="theme-picker-wrap">
    <button ref="trigger" type="button" class="theme-picker-button" aria-label="Choose dashboard colors" title="Choose dashboard colors" :aria-expanded="open" aria-haspopup="menu" @click="open ? closeMenu() : showMenu()" @keydown="handleTriggerKeydown">
      <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 3a9 9 0 1 0 0 18h1.4a2 2 0 0 0 1.7-3l-.4-.7a1.5 1.5 0 0 1 1.3-2.3h1a4 4 0 0 0 4-4c0-4.4-4-8-9-8Z"/><circle cx="7.5" cy="11" r="1"/><circle cx="10" cy="7.5" r="1"/><circle cx="15" cy="7.5" r="1"/></svg>
      <span class="theme-picker-button-swatches" aria-hidden="true"><i v-for="color in selected.colors" :key="color" :style="{ background: color }" /></span>
    </button>
    <section v-if="open" class="theme-picker-menu" role="menu" aria-label="Dashboard color schemes" @keydown="handleMenuKeydown">
      <header><strong>Dashboard color schemes</strong><small>Choose a palette for this browser</small></header>
      <div>
        <button v-for="(theme,index) in themes" :key="theme.id" :ref="(element) => setOption(element as Element | null, index)" type="button" role="menuitemradio" :aria-checked="theme.id === modelValue" :class="{ selected: theme.id === modelValue }" @click="choose(theme.id)">
          <span class="theme-option-swatches" aria-hidden="true"><i v-for="color in theme.colors" :key="color" :style="{ background: color }" /></span>
          <span><strong>{{ theme.name }}</strong><small>{{ theme.description }} · {{ theme.scheme }}</small></span>
          <b aria-hidden="true">{{ theme.id === modelValue ? '✓' : '' }}</b>
        </button>
      </div>
    </section>
  </div>
</template>
