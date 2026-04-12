<template>
  <div
    class="w-full h-1.5 rounded-full overflow-hidden"
    :style="{ background: 'var(--surface-elevated)' }"
  >
    <div
      class="h-full rounded-full transition-[width] duration-500 ease-out"
      :class="{ 'animate-pulse': indeterminate }"
      :style="{
        width: `${clamped}%`,
        background: color,
      }"
    />
  </div>
</template>

<script setup lang="ts">
const props = withDefaults(
  defineProps<{
    value?: number
    indeterminate?: boolean
    tone?: "brand" | "success" | "warning" | "error"
  }>(),
  {
    value: 0,
    indeterminate: false,
    tone: "brand",
  },
)

const clamped = computed(() => Math.max(0, Math.min(100, props.value)))

const tones: Record<string, string> = {
  brand: "var(--brand-600)",
  success: "var(--status-success)",
  warning: "var(--status-warning)",
  error: "var(--status-error)",
}

const color = computed(() => tones[props.tone] ?? tones.brand!)
</script>
