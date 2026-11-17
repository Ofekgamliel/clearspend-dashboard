<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref, watch } from 'vue';
import { modalFocus as vModalFocus } from '../modalFocus';
import UiIconButton from './UiIconButton.vue';

type CloseReason = 'escape' | 'backdrop' | 'close-button' | 'completed';
const props = withDefaults(defineProps<{
  open: boolean;
  titleId: string;
  descriptionId?: string;
  size?: 'large' | 'compact';
  closeLabel: string;
  layer?: 'base' | 'nested';
  dismissible?: boolean;
}>(), { descriptionId: undefined, size: 'large', layer: 'base', dismissible: true });
const emit = defineEmits<{ requestClose: [reason: CloseReason] }>();
const dialog = ref<HTMLElement | null>(null);

function isTopmost(): boolean {
  const dialogs = [...document.querySelectorAll<HTMLElement>('[data-ui-dialog]')];
  return dialog.value !== null && dialogs.at(-1) === dialog.value;
}
function keydown(event: KeyboardEvent): void {
  if (event.key === 'Escape' && props.open && props.dismissible && isTopmost()) emit('requestClose', 'escape');
}
function backdrop(): void {
  if (props.dismissible) emit('requestClose', 'backdrop');
}
function syncScrollLock(): void {
  document.body.classList.toggle('ui-dialog-open', Boolean(document.querySelector('[data-ui-dialog]')));
}
watch(() => props.open, () => requestAnimationFrame(syncScrollLock));
onMounted(() => document.addEventListener('keydown', keydown));
onBeforeUnmount(() => { document.removeEventListener('keydown', keydown); requestAnimationFrame(syncScrollLock); });
</script>

<template>
  <Teleport to="body">
    <div v-if="open" class="ui-dialog-backdrop" :class="{ 'ui-dialog-backdrop--nested': layer === 'nested' }" @mousedown.self="backdrop">
      <section ref="dialog" v-modal-focus class="ui-dialog" :class="`ui-dialog--${size}`" data-ui-dialog role="dialog" aria-modal="true" :aria-labelledby="titleId" :aria-describedby="descriptionId">
        <UiIconButton class="ui-dialog__close" :label="closeLabel" size="compact" @click="emit('requestClose', 'close-button')">×</UiIconButton>
        <header v-if="$slots.header" class="ui-dialog__header"><slot name="header" /></header>
        <div class="ui-dialog__body"><slot /></div>
        <footer v-if="$slots.footer" class="ui-dialog__footer"><slot name="footer" /></footer>
      </section>
    </div>
  </Teleport>
</template>

<style scoped>
.ui-dialog-backdrop{position:fixed;z-index:110;inset:0;display:grid;place-items:center;padding:17px;background:var(--ui-overlay);backdrop-filter:blur(3px)}.ui-dialog-backdrop--nested{z-index:125;background:var(--ui-overlay-nested)}.ui-dialog{position:relative;overflow:hidden;border:1px solid var(--ui-dialog-border);background:var(--ui-surface);box-shadow:0 24px 70px var(--ui-dialog-shadow)}.ui-dialog--compact{width:min(400px,calc(100vw - 28px));border-radius:15px}.ui-dialog--large{width:min(980px,100%);max-height:90vh;overflow:auto;border-radius:16px}.ui-dialog__close{position:absolute;z-index:3;top:10px;right:12px;font-size:24px}.ui-dialog__header{padding:17px 52px 13px 18px;border-bottom:1px solid var(--ui-divider)}.ui-dialog__header :deep(h2){margin:0;color:var(--ui-heading);font-size:17px}.ui-dialog__header :deep(p){margin:4px 0 0;color:var(--ui-subtle);font-size:10px;line-height:1.45}.ui-dialog--compact .ui-dialog__body{padding:15px 18px 16px}.ui-dialog__footer{display:flex;justify-content:flex-end;gap:8px;padding:10px 18px;border-top:1px solid var(--ui-divider);background:var(--ui-footer)}:global(body.ui-dialog-open){overflow:hidden}
</style>
