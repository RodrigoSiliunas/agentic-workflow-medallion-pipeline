<template>
  <code
    class="inline-flex items-center px-1.5 py-0.5 font-[var(--font-mono)] text-[11px] rounded-[var(--radius-sm)] align-middle"
    :style="toneStyle"
  >
    <slot />
  </code>
</template>

<script setup lang="ts">
const props = withDefaults(
  defineProps<{
    variant?: "default" | "subtle" | "brand"
  }>(),
  {
    variant: "default",
  },
)

const STYLES = {
  default: {
    background: "var(--surface-elevated)",
    color: "var(--text-primary)",
    border: "1px solid var(--border)",
  },
  subtle: {
    background: "transparent",
    color: "var(--text-secondary)",
    border: "1px solid var(--border-subtle)",
  },
  brand: {
    background: "rgba(127,34,254,0.10)",
    color: "var(--brand-400)",
    border: "1px solid rgba(127,34,254,0.25)",
  },
}

const toneStyle = computed(() => STYLES[props.variant])
</script>
