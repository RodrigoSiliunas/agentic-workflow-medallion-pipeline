<template>
  <span
    class="relative inline-block rounded-full align-middle"
    :class="pulse ? 'status-pulse' : ''"
    :style="dotStyle"
    :aria-label="ariaLabel"
    :role="ariaLabel ? 'status' : undefined"
  >
    <span
      v-if="pulse"
      class="absolute inset-0 rounded-full ping-ring"
      :style="{ background: color }"
      aria-hidden="true"
    />
  </span>
</template>

<script setup lang="ts">
type Tone = "neutral" | "brand" | "success" | "warning" | "error" | "info"

const props = withDefaults(
  defineProps<{
    tone?: Tone
    size?: number
    pulse?: boolean
    ariaLabel?: string
  }>(),
  {
    tone: "neutral",
    size: 6,
    pulse: false,
    ariaLabel: undefined,
  },
)

const TONE_COLORS: Record<Tone, string> = {
  neutral: "var(--text-tertiary)",
  brand: "var(--brand-500)",
  success: "var(--status-success)",
  warning: "var(--status-warning)",
  error: "var(--status-error)",
  info: "var(--status-info)",
}

const color = computed(() => TONE_COLORS[props.tone])

const dotStyle = computed(() => ({
  width: `${props.size}px`,
  height: `${props.size}px`,
  background: color.value,
}))
</script>
