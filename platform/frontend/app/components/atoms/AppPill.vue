<template>
  <span
    class="inline-flex items-center gap-1.5 px-2 py-0.5 rounded-[var(--radius-full)] font-medium"
    :class="sizeClasses"
    :style="toneStyle"
  >
    <span
      v-if="dot"
      class="inline-block rounded-full"
      :class="pulse ? 'status-pulse' : ''"
      :style="dotStyle"
    />
    <AppIcon
      v-if="icon"
      :name="icon"
      :size="iconSize"
    />
    <slot />
  </span>
</template>

<script setup lang="ts">
type Tone = "neutral" | "brand" | "success" | "warning" | "error" | "info"

const props = withDefaults(
  defineProps<{
    tone?: Tone
    size?: "xs" | "sm"
    dot?: boolean
    pulse?: boolean
    icon?: string
  }>(),
  {
    tone: "neutral",
    size: "sm",
    dot: false,
    pulse: false,
    icon: undefined,
  },
)

const TONES: Record<Tone, { bg: string; fg: string; border: string; dot: string }> = {
  neutral: {
    bg: "var(--surface-elevated)",
    fg: "var(--text-secondary)",
    border: "var(--border)",
    dot: "var(--text-tertiary)",
  },
  brand: {
    bg: "rgba(127,34,254,0.12)",
    fg: "var(--brand-400)",
    border: "rgba(127,34,254,0.3)",
    dot: "var(--brand-500)",
  },
  success: {
    bg: "rgba(16,185,129,0.12)",
    fg: "var(--status-success)",
    border: "rgba(16,185,129,0.3)",
    dot: "var(--status-success)",
  },
  warning: {
    bg: "rgba(245,158,11,0.12)",
    fg: "var(--status-warning)",
    border: "rgba(245,158,11,0.3)",
    dot: "var(--status-warning)",
  },
  error: {
    bg: "rgba(239,68,68,0.12)",
    fg: "var(--status-error)",
    border: "rgba(239,68,68,0.3)",
    dot: "var(--status-error)",
  },
  info: {
    bg: "rgba(59,130,246,0.12)",
    fg: "var(--status-info)",
    border: "rgba(59,130,246,0.3)",
    dot: "var(--status-info)",
  },
}

const sizeClasses = computed(() =>
  props.size === "xs" ? "text-[10px] py-px" : "text-[11px]",
)

const iconSize = computed(() => (props.size === "xs" ? "xs" : "sm"))

const toneStyle = computed(() => {
  const t = TONES[props.tone]
  return {
    background: t.bg,
    color: t.fg,
    border: `1px solid ${t.border}`,
  }
})

const dotStyle = computed(() => ({
  width: props.size === "xs" ? "4px" : "6px",
  height: props.size === "xs" ? "4px" : "6px",
  background: TONES[props.tone].dot,
}))
</script>
