<template>
  <LandingCardShell
    eyebrow="Sua plataforma em números"
    title="Tudo medido. Nada opaco."
    description="Custo de tokens, PRs automáticos, taxa de sucesso e economia por dedup — tudo agregado em tempo real."
  >
    <div class="px-6 pb-6 grid grid-cols-2 md:grid-cols-4 gap-3">
      <div
        v-for="m in metrics"
        :key="m.label"
        class="rounded-[var(--radius-md)] border p-3"
        :style="{ borderColor: 'var(--border)', background: 'var(--bg)' }"
      >
        <div class="flex items-center gap-1.5 mb-1">
          <span
            class="inline-flex items-center gap-1 text-[9px] uppercase tracking-wider font-semibold"
            :style="{ color: 'var(--text-tertiary)' }"
          >{{ m.label }}</span>
        </div>
        <p
          class="text-xl font-semibold tabular-nums tracking-tight"
          :style="{ color: 'var(--text-primary)' }"
        >
          {{ m.value }}
        </p>
        <div class="flex items-center gap-1.5 mt-0.5">
          <span
            class="text-[10px] font-medium tabular-nums"
            :style="{ color: m.trend.startsWith('-') ? 'var(--status-error)' : 'var(--status-success)' }"
          >{{ m.trend }}</span>
          <span class="text-[10px]" :style="{ color: 'var(--text-tertiary)' }">
            vs 7d
          </span>
        </div>
        <!-- Sparkline SVG -->
        <svg
          class="mt-2 w-full"
          viewBox="0 0 100 28"
          preserveAspectRatio="none"
          style="height: 32px"
        >
          <!-- Gradient fill -->
          <defs>
            <linearGradient :id="`grad-${m.label}`" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" :stop-color="m.color" stop-opacity="0.35" />
              <stop offset="100%" :stop-color="m.color" stop-opacity="0" />
            </linearGradient>
          </defs>
          <!-- Area fill -->
          <path
            :d="areaPath(m.points)"
            :fill="`url(#grad-${m.label})`"
          />
          <!-- Line stroke -->
          <path
            :d="linePath(m.points)"
            fill="none"
            :stroke="m.color"
            stroke-width="1.5"
            stroke-linecap="round"
            stroke-linejoin="round"
          />
          <!-- Last point marker -->
          <circle
            :cx="lastX(m.points)"
            :cy="lastY(m.points)"
            r="2"
            :fill="m.color"
          />
        </svg>
      </div>
    </div>
  </LandingCardShell>
</template>

<script setup lang="ts">
interface Metric {
  label: string
  value: string
  trend: string
  color: string
  points: number[]
}

const metrics: Metric[] = [
  {
    label: "Deploys / sem",
    value: "47",
    trend: "+12%",
    color: "#7f22fe",
    points: [18, 24, 20, 28, 32, 30, 36, 42, 38, 44, 47],
  },
  {
    label: "Taxa de sucesso",
    value: "96.4%",
    trend: "+2.1%",
    color: "#10b981",
    points: [89, 91, 88, 92, 93, 90, 94, 95, 96, 95, 96.4],
  },
  {
    label: "PRs automáticos",
    value: "19",
    trend: "+6",
    color: "#8e51f6",
    points: [4, 6, 7, 9, 10, 13, 13, 15, 16, 18, 19],
  },
  {
    label: "Custo / mês",
    value: "$4.82",
    trend: "-18%",
    color: "#3b82f6",
    points: [6.8, 6.1, 6.4, 5.9, 5.7, 5.4, 5.2, 5.0, 4.9, 4.85, 4.82],
  },
]

function normalize(points: number[]): Array<[number, number]> {
  const min = Math.min(...points)
  const max = Math.max(...points)
  const range = max - min || 1
  const w = 100
  const h = 24
  return points.map((p, i) => {
    const x = (i / (points.length - 1)) * w
    const y = h - ((p - min) / range) * h + 2
    return [x, y]
  })
}

function linePath(points: number[]): string {
  const coords = normalize(points)
  return coords.map(([x, y], i) => `${i === 0 ? "M" : "L"}${x.toFixed(1)},${y.toFixed(1)}`).join(" ")
}

function areaPath(points: number[]): string {
  const coords = normalize(points)
  const line = coords.map(([x, y], i) => `${i === 0 ? "M" : "L"}${x.toFixed(1)},${y.toFixed(1)}`).join(" ")
  const last = coords[coords.length - 1]!
  const first = coords[0]!
  return `${line} L${last[0].toFixed(1)},28 L${first[0].toFixed(1)},28 Z`
}

function lastX(points: number[]): number {
  return normalize(points)[points.length - 1]![0]
}

function lastY(points: number[]): number {
  return normalize(points)[points.length - 1]![1]
}
</script>
