<template>
  <span
    class="inline-flex items-center rounded-full px-2 py-0.5 text-[10px] font-medium uppercase tracking-wider"
    :style="{
      background: bg,
      color: fg,
      border: `1px solid ${border}`,
    }"
  >
    <slot />
  </span>
</template>

<script setup lang="ts">
const props = withDefaults(
  defineProps<{
    tone?: "neutral" | "brand" | "success" | "warning" | "error" | "info"
  }>(),
  { tone: "neutral" },
)

const tones: Record<string, { bg: string; fg: string; border: string }> = {
  neutral: {
    bg: "var(--surface-elevated)",
    fg: "var(--text-secondary)",
    border: "var(--border)",
  },
  brand: {
    bg: "rgba(127,34,254,0.12)",
    fg: "var(--brand-500)",
    border: "rgba(127,34,254,0.3)",
  },
  success: {
    bg: "rgba(16,185,129,0.12)",
    fg: "var(--status-success)",
    border: "rgba(16,185,129,0.3)",
  },
  warning: {
    bg: "rgba(245,158,11,0.12)",
    fg: "var(--status-warning)",
    border: "rgba(245,158,11,0.3)",
  },
  error: {
    bg: "rgba(239,68,68,0.12)",
    fg: "var(--status-error)",
    border: "rgba(239,68,68,0.3)",
  },
  info: {
    bg: "rgba(59,130,246,0.12)",
    fg: "var(--status-info)",
    border: "rgba(59,130,246,0.3)",
  },
}

const bg = computed(() => tones[props.tone]?.bg ?? tones.neutral!.bg)
const fg = computed(() => tones[props.tone]?.fg ?? tones.neutral!.fg)
const border = computed(() => tones[props.tone]?.border ?? tones.neutral!.border)
</script>
