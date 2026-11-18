<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref, watch } from 'vue';
import { modalFocus as vModalFocus } from '../accessibility/modalFocus';
import UiIconButton from './UiIconButton.vue';

type CloseReason = 'escape' | 'backdrop' | 'close-button' | 'completed';
const props = withDefaults(defineProps<{
  open: boolean;
  titleId: string;
  descriptionId?: string;
  size?: 'management' | 'analysis' | 'browser' | 'large' | 'insight' | 'standard' | 'wide' | 'medium' | 'compact';
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
.ui-dialog-backdrop{position:fixed;z-index:110;inset:0;display:grid;place-items:center;padding:17px;background:var(--ui-overlay);backdrop-filter:blur(3px)}.ui-dialog-backdrop--nested{z-index:125;background:var(--ui-overlay-nested)}.ui-dialog{position:relative;overflow:hidden;border:1px solid var(--ui-dialog-border);background:var(--ui-surface);box-shadow:0 24px 70px var(--ui-dialog-shadow)}.ui-dialog--compact{width:min(400px,calc(100vw - 28px));border-radius:15px}.ui-dialog--medium{width:min(590px,calc(100vw - 28px));border-radius:16px}.ui-dialog--wide{width:min(640px,calc(100vw - 28px));border-radius:16px}.ui-dialog--standard{width:min(760px,100%);max-height:min(84vh,760px);display:flex;flex-direction:column;border:0;border-radius:16px;box-shadow:0 25px 70px var(--ui-dialog-shadow)}.ui-dialog--large{width:min(980px,100%);max-height:90vh;overflow:auto;border:0;border-radius:16px;box-shadow:0 25px 70px var(--ui-dialog-shadow)}.ui-dialog--browser{width:min(1040px,100%);height:min(82vh,760px);display:flex;flex-direction:column;border:0;border-radius:16px;box-shadow:0 25px 70px var(--ui-dialog-shadow)}.ui-dialog__close{position:absolute;z-index:3;top:10px;right:12px;font-size:24px}.ui-dialog--standard .ui-dialog__close,.ui-dialog--large .ui-dialog__close,.ui-dialog--browser .ui-dialog__close{top:13px;right:16px}.ui-dialog__header{padding:17px 52px 13px 18px;border-bottom:1px solid var(--ui-divider)}.ui-dialog__header :deep(h2){margin:0;color:var(--ui-heading);font-size:17px}.ui-dialog__header :deep(p){margin:4px 0 0;color:var(--ui-subtle);font-size:10px;line-height:1.45}.ui-dialog--standard .ui-dialog__header{padding:22px 55px 15px 24px}.ui-dialog--standard .ui-dialog__header :deep(h2){font-size:21px;letter-spacing:-.03em}.ui-dialog--large .ui-dialog__header{padding:21px 58px 15px 25px}.ui-dialog--large .ui-dialog__header :deep(h2){font-size:22px}.ui-dialog--large .ui-dialog__header :deep(p){margin-top:6px}.ui-dialog--browser .ui-dialog__header{padding:23px 55px 15px 25px}.ui-dialog--browser .ui-dialog__header :deep(h2){font-size:23px;letter-spacing:-.03em}.ui-dialog--browser .ui-dialog__header :deep(p){margin-top:6px}.ui-dialog--compact .ui-dialog__body{padding:15px 18px 16px}.ui-dialog--medium .ui-dialog__body,.ui-dialog--wide .ui-dialog__body{padding:0 22px}.ui-dialog--standard .ui-dialog__body,.ui-dialog--browser .ui-dialog__body{min-height:0;display:flex;flex:1;flex-direction:column;overflow:hidden}.ui-dialog--large .ui-dialog__body{padding:15px 25px 22px}.ui-dialog--medium .ui-dialog__header,.ui-dialog--wide .ui-dialog__header{padding:22px 52px 0 22px;border-bottom:0}.ui-dialog--medium .ui-dialog__footer,.ui-dialog--wide .ui-dialog__footer{margin-top:17px;padding:0 22px 22px;border-top:0;background:transparent}.ui-dialog__footer{display:flex;justify-content:flex-end;gap:8px;padding:10px 18px;border-top:1px solid var(--ui-divider);background:var(--ui-footer)}:global(body.ui-dialog-open){overflow:hidden}@media(max-width:700px){.ui-dialog-backdrop{padding:8px}.ui-dialog--browser{height:91vh}.ui-dialog--browser .ui-dialog__header{padding-left:16px}}
.ui-dialog--analysis{width:min(1180px,100%);height:min(88vh,850px);display:flex;flex-direction:column;border:0;border-radius:16px;box-shadow:0 25px 70px var(--ui-dialog-shadow)}.ui-dialog--analysis .ui-dialog__close{top:13px;right:16px}.ui-dialog--analysis .ui-dialog__header{padding:24px 58px 17px 27px}.ui-dialog--analysis .ui-dialog__header :deep(h2){font-size:22px}.ui-dialog--analysis .ui-dialog__body{min-height:0;display:flex;flex:1;flex-direction:column;overflow:hidden}@media(max-width:700px){.ui-dialog--analysis{height:94vh}}
.ui-dialog--insight{width:min(720px,calc(100% - 16px));max-height:min(86vh,780px);overflow:auto;border-radius:15px;box-shadow:0 28px 90px var(--ui-dialog-shadow)}.ui-dialog--insight .ui-dialog__close{top:15px;right:15px}.ui-dialog--insight .ui-dialog__header{padding:24px 54px 18px 27px}.ui-dialog--insight .ui-dialog__body{padding:20px 27px}.ui-dialog--insight .ui-dialog__footer{padding:15px 27px}@media(max-width:700px){.ui-dialog--insight{width:calc(100% - 8px)}.ui-dialog--insight .ui-dialog__header,.ui-dialog--insight .ui-dialog__body,.ui-dialog--insight .ui-dialog__footer{padding-right:18px;padding-left:18px}}
.ui-dialog--management{width:min(1080px,100%);height:min(84vh,760px);display:flex;flex-direction:column;border:0;border-radius:16px;box-shadow:0 25px 70px var(--ui-dialog-shadow)}.ui-dialog--management .ui-dialog__close{top:13px;right:16px}.ui-dialog--management .ui-dialog__header{padding:20px 54px 16px 24px}.ui-dialog--management .ui-dialog__header :deep(h2){font-size:22px;letter-spacing:-.03em}.ui-dialog--management .ui-dialog__body{min-height:0;display:flex;flex:1;flex-direction:column;overflow:hidden}@media(max-width:700px){.ui-dialog--management{height:94vh}}
</style>
