<script setup lang="ts">
defineOptions({ inheritAttrs: false });
withDefaults(defineProps<{ modelValue: string | number; invalid?: boolean }>(), { invalid: false });
const emit = defineEmits<{ 'update:modelValue': [value: string] }>();
</script>
<template><input class="ui-input" v-bind="$attrs" :value="modelValue" :aria-invalid="invalid || undefined" @input="emit('update:modelValue', ($event.target as HTMLInputElement).value)"></template>
<style scoped>
.ui-input{display:block;width:100%;height:36px;padding:0 10px;border:1px solid var(--ui-border);border-radius:8px;background:var(--ui-surface);color:var(--ui-text);font:600 10px/1 inherit;outline:0}.ui-input:focus{border-color:var(--ui-focus-border);box-shadow:0 0 0 3px var(--ui-focus-soft)}.ui-input[aria-invalid=true]{border-color:var(--ui-danger)}.ui-input:disabled{cursor:not-allowed;opacity:.6}
</style>
