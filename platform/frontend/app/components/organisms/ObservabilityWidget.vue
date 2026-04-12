<template>
  <section v-if="metrics" class="mb-10">
    <div class="flex items-baseline justify-between mb-3">
      <h2
        class="text-sm font-semibold uppercase tracking-wider"
        :style="{ color: 'var(--text-tertiary)' }"
      >
        Sua plataforma em números
      </h2>
      <p class="text-[10px]" :style="{ color: 'var(--text-tertiary)' }">
        Últimos {{ metrics.observer.periodDays }} dias
      </p>
    </div>

    <div class="grid grid-cols-2 md:grid-cols-4 gap-3">
      <MetricCard
        label="Pipelines"
        :value="metrics.pipelines.total"
        icon="cpu-chip"
        :hint="`${metrics.pipelines.withDatabricksJob} com job Databricks`"
      />
      <MetricCard
        label="Deploys"
        :value="metrics.deployments.total"
        icon="rocket-launch"
        icon-color="var(--status-success)"
        :hint="deploysHint"
      />
      <MetricCard
        label="Canais ativos"
        :value="`${metrics.channels.connected}/${metrics.channels.total}`"
        icon="phone"
        icon-color="var(--status-info)"
        :hint="channelsHint"
      />
      <MetricCard
        label="Observer"
        :value="`$${metrics.observer.estimatedCostUsd.toFixed(2)}`"
        icon="sparkles"
        icon-color="var(--brand-500)"
        :hint="`${metrics.observer.prsCreated} PRs automáticos`"
      />
    </div>
  </section>
</template>

<script setup lang="ts">
import type { ObservabilityMetrics } from "~/types/observability"

const metrics = ref<ObservabilityMetrics | null>(null)

const deploysHint = computed(() => {
  if (!metrics.value) return ""
  const d = metrics.value.deployments
  const avg = d.avgDurationSeconds ? ` · ${Math.round(d.avgDurationSeconds)}s avg` : ""
  return `${d.success} sucesso · ${d.failed} falha${avg}`
})

const channelsHint = computed(() => {
  if (!metrics.value) return ""
  const kinds = Object.keys(metrics.value.channels.byChannel)
  if (kinds.length === 0) return "Nenhum canal"
  return kinds.join(" · ")
})

onMounted(async () => {
  try {
    const api = useObservabilityApi()
    metrics.value = await api.getMetrics()
  } catch {
    // silencioso — widget so aparece se os dados chegarem
  }
})
</script>
