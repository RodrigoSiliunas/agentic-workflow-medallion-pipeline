<template>
  <button
    type="button"
    class="flex cursor-pointer flex-col items-start gap-1.5 rounded-[var(--radius-lg)] border border-[var(--border)] bg-[var(--surface)] p-[12px_14px] text-left transition-all duration-150 hover:border-[rgba(142,81,246,0.4)] hover:bg-[var(--surface-elevated)] focus-visible:outline-none focus-visible:shadow-[var(--shadow-focus)]"
    @click="emit('click', title)"
  >
    <AppIcon :name="icon" size="sm" :style="{ color: 'var(--brand-500)' }" />
    <span
      class="text-[12px] font-medium leading-[1.4]"
      :style="{ color: 'var(--fg-primary)' }"
    >
      {{ title }}
    </span>
    <AppCode class="text-[10px]">{{ hint }}</AppCode>
  </button>
</template>

<script setup lang="ts">
defineProps<{
  icon: string
  title: string
  hint: string
}>()

const emit = defineEmits<{
  click: [suggestion: string]
}>()
</script>
