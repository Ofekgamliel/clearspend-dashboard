<script setup lang="ts">
defineOptions({ inheritAttrs: false });
withDefaults(defineProps<{ modelValue: string | number; invalid?: boolean }>(), { invalid: false });
const emit = defineEmits<{ 'update:modelValue': [value: string] }>();
</script>
<template><select class="ui-select" v-bind="$attrs" :value="modelValue" :aria-invalid="invalid || undefined" @change="emit('update:modelValue', ($event.target as HTMLSelectElement).value)"><slot /></select></template>
<style scoped>
.ui-select{display:block;width:100%;height:36px;padding:0 29px 0 10px;border:1px solid var(--ui-border);border-radius:8px;appearance:none;background-color:var(--ui-surface);background-image:linear-gradient(45deg,transparent 50%,var(--ui-muted) 50%),linear-gradient(135deg,var(--ui-muted) 50%,transparent 50%);background-position:calc(100% - 12px) 15px,calc(100% - 8px) 15px;background-repeat:no-repeat;background-size:4px 4px;color:var(--ui-text);font:600 10px/1 inherit;outline:0}.ui-select:focus{border-color:var(--ui-focus-border);box-shadow:0 0 0 3px var(--ui-focus-soft)}.ui-select[aria-invalid=true]{border-color:var(--ui-danger)}.ui-select:disabled{cursor:not-allowed;opacity:.6}
</style>
