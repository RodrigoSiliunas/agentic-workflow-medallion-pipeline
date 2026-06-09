<template>
  <div
    class="inline-flex flex-col items-center gap-1"
    role="img"
    :aria-label="`Risco ${clamped} de 10`"
  >
    <svg
      :width="size"
      :height="size / 2 + 10"
      :viewBox="`0 0 ${size} ${size / 2 + 14}`"
      class="overflow-visible"
    >
      <!-- Arco de fundo -->
      <path
        :d="bgPath"
        fill="none"
        stroke="var(--border)"
        stroke-width="8"
        stroke-linecap="round"
      />
      <!-- Arco de valor -->
      <path
        :d="valuePath"
        fill="none"
        :stroke="valueColor"
        stroke-width="8"
        stroke-linecap="round"
        class="transition-all duration-300"
      />
      <!-- Score numérico com 1 casa decimal -->
      <text
        :x="cx"
        :y="cy - 2"
        text-anchor="middle"
        :style="{
          fontFamily: 'var(--font-sans)',
          fontSize: '22px',
          fontWeight: 600,
          fill: 'var(--fg-primary)',
          letterSpacing: '-0.02em',
        }"
      >{{ display }}</text>
      <!-- Denominador -->
      <text
        :x="cx"
        :y="cy + 12"
        text-anchor="middle"
        :style="{ fontFamily: 'var(--font-mono)', fontSize: '9px', fill: 'var(--fg-tertiary)' }"
      >/ 10</text>
    </svg>

    <!-- Badge de nível -->
    <AppPill :tone="tone" dot size="xs">{{ label }}</AppPill>
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

const clamped = computed(() => Math.max(0, Math.min(10, props.value)))
const display = computed(() => clamped.value.toFixed(1))

const r = computed(() => (props.size - 14) / 2)
const cx = computed(() => props.size / 2)
const cy = computed(() => props.size / 2)

function polar(deg: number): [number, number] {
  const rad = ((deg - 180) * Math.PI) / 180
  return [cx.value + r.value * Math.cos(rad), cy.value + r.value * Math.sin(rad)]
}

const angle = computed(() => (clamped.value / 10) * 180)

const bgPath = computed(() => {
  const [x0, y0] = polar(0)
  return `M ${x0} ${y0} A ${r.value} ${r.value} 0 1 1 ${cx.value + r.value} ${cy.value}`
})

const valuePath = computed(() => {
  const [x0, y0] = polar(0)
  const [x1, y1] = polar(angle.value)
  const large = angle.value > 180 ? 1 : 0
  return `M ${x0} ${y0} A ${r.value} ${r.value} 0 ${large} 1 ${x1} ${y1}`
})

const valueColor = computed(() => {
  if (clamped.value <= 3) return "var(--status-success)"
  if (clamped.value <= 6) return "var(--status-warning)"
  return "var(--status-error)"
})

const tone = computed(() => {
  if (clamped.value <= 3) return "success" as const
  if (clamped.value <= 6) return "warning" as const
  return "error" as const
})

const label = computed(() => {
  if (clamped.value <= 3) return "Baixo"
  if (clamped.value <= 6) return "Médio"
  return "Alto"
})
</script>
