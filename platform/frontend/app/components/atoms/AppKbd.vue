<template>
  <UKbd
    :size="size"
    :variant="variant"
    :ui="{
      base: 'inline-flex items-center justify-center rounded-[var(--radius-sm)] border border-[var(--border)] bg-[var(--surface-elevated)] text-[var(--text-secondary)] font-[var(--font-mono)] text-[10px] px-1.5 min-w-[20px]',
    }"
  >
    <slot />
  </UKbd>
</template>

<script setup lang="ts">
withDefaults(
  defineProps<{
    size?: "sm" | "md" | "lg"
    variant?: "solid" | "outline" | "subtle"
  }>(),
  {
    size: "sm",
    variant: "outline",
  },
)
</script>
