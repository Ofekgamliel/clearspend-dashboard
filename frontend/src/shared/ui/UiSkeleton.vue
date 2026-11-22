<script setup lang="ts">
withDefaults(defineProps<{
  shape?: 'line' | 'block' | 'circle';
}>(), { shape: 'block' });
</script>

<template>
  <span class="ui-skeleton" :class="`ui-skeleton--${shape}`" aria-hidden="true" />
</template>

<style scoped>
.ui-skeleton{position:relative;display:block;overflow:hidden;background:var(--ui-skeleton-base)}
.ui-skeleton::after{position:absolute;inset:0;content:"";background:linear-gradient(100deg,transparent 20%,var(--ui-skeleton-highlight) 48%,transparent 76%);transform:translateX(-100%);animation:ui-skeleton-shimmer 1.45s ease-in-out infinite}
.ui-skeleton--line{height:.75rem;border-radius:999px}
.ui-skeleton--block{border-radius:10px}
.ui-skeleton--circle{aspect-ratio:1;border-radius:50%}
@keyframes ui-skeleton-shimmer{to{transform:translateX(100%)}}
@media (prefers-reduced-motion:reduce){.ui-skeleton::after{display:none}}
@media (forced-colors:active){.ui-skeleton{border:1px solid CanvasText;background:Canvas}.ui-skeleton::after{display:none}}
</style>
