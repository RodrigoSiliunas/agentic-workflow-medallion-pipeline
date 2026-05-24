<template>
  <div
    class="relative inline-flex flex-col items-center justify-end"
    :style="{ width: `${size}px`, height: `${size / 2 + 12}px` }"
    role="img"
    :aria-label="`Risco ${clamped} de 10`"
  >
    <svg
      :width="size"
      :height="size / 2"
      :viewBox="`0 0 ${size} ${size / 2}`"
      class="overflow-visible"
    >
      <!-- Background arc -->
      <path
        :d="arcPath(1)"
        fill="none"
        :stroke="trackColor"
        :stroke-width="strokeWidth"
        stroke-linecap="round"
      />
      <!-- Value arc -->
      <path
        :d="arcPath(progress)"
        fill="none"
        :stroke="valueColor"
        :stroke-width="strokeWidth"
        stroke-linecap="round"
        class="transition-all duration-300"
      />
    </svg>
    <div class="absolute top-[40%] inset-x-0 flex flex-col items-center pointer-events-none">
      <span class="font-[var(--font-mono)] text-base leading-none" :style="{ color: valueColor }">
        {{ clamped }}
      </span>
      <span class="caption text-[10px] leading-none mt-0.5">{{ label }}</span>
    </div>
  </div>
</template>

<script setup lang="ts">
const props = withDefaults(
  defineProps<{
    value: number
    size?: number
  }>(),
  {
    size: 88,
  },
)

const clamped = computed(() => Math.max(0, Math.min(10, Math.round(props.value))))
const progress = computed(() => clamped.value / 10)

const strokeWidth = computed(() => Math.max(6, Math.round(props.size / 12)))
const trackColor = "var(--surface-elevated)"

const valueColor = computed(() => {
  if (clamped.value >= 7) return "var(--status-error)"
  if (clamped.value >= 4) return "var(--status-warning)"
  return "var(--status-success)"
})

const label = computed(() => {
  if (clamped.value >= 7) return "alto"
  if (clamped.value >= 4) return "medio"
  return "baixo"
})

function arcPath(t: number) {
  const w = props.size
  const cx = w / 2
  const cy = w / 2
  const r = w / 2 - strokeWidth.value / 2
  const startAngle = Math.PI
  const endAngle = Math.PI + Math.PI * t
  const x1 = cx + r * Math.cos(startAngle)
  const y1 = cy + r * Math.sin(startAngle)
  const x2 = cx + r * Math.cos(endAngle)
  const y2 = cy + r * Math.sin(endAngle)
  const largeArc = t > 0.5 ? 1 : 0
  return `M ${x1} ${y1} A ${r} ${r} 0 ${largeArc} 1 ${x2} ${y2}`
}
</script>
