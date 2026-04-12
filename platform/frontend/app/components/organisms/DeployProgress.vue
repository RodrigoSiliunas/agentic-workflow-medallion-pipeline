<template>
  <div class="flex-1 flex flex-col overflow-hidden">
    <!-- Header -->
    <header
      class="px-8 py-4 border-b"
      :style="{ borderColor: 'var(--border)' }"
    >
      <div class="flex items-center gap-3 mb-3">
        <AppButton
          variant="ghost"
          size="sm"
          icon="i-heroicons-arrow-left"
          square
          to="/deployments"
        />
        <div class="flex-1 min-w-0">
          <div class="flex items-center gap-2">
            <h1 class="text-sm font-semibold tracking-tight truncate" :style="{ color: 'var(--text-primary)' }">
              {{ deployment.config.name }}
            </h1>
            <AppBadge :color="statusColor" variant="subtle">
              {{ statusLabel }}
            </AppBadge>
          </div>
          <p class="text-[11px]" :style="{ color: 'var(--text-tertiary)' }">
            {{ deployment.templateName }} · {{ deployment.config.environment }} ·
            {{ relativeTime(deployment.createdAt) }}
          </p>
        </div>
        <AppButton
          v-if="deployment.status === 'success' && deployment.pipelineId"
          size="sm"
          icon="i-heroicons-chat-bubble-left-right"
          @click="openPipelineChat"
        >
          Abrir chat
        </AppButton>
        <AppButton
          v-else-if="deployment.status === 'running'"
          variant="outline"
          size="sm"
          icon="i-heroicons-stop"
          @click="deploymentsStore.cancel(deployment.id)"
        >
          Cancelar
        </AppButton>
        <slot name="actions" />
      </div>
      <ProgressBar :value="progressPercent" :tone="progressTone" />
      <p class="text-[10px] mt-1.5 text-right tabular-nums" :style="{ color: 'var(--text-tertiary)' }">
        {{ completedSteps }} / {{ deployment.steps.length }} etapas
        <span v-if="deployment.durationMs"> · {{ formatDuration(deployment.durationMs) }}</span>
      </p>
    </header>

    <!-- Body: 2 colunas (saga steps + logs) -->
    <div class="flex-1 grid grid-cols-1 lg:grid-cols-5 gap-0 overflow-hidden">
      <!-- Saga steps -->
      <section
        class="lg:col-span-2 border-r overflow-y-auto p-4 space-y-2"
        :style="{ borderColor: 'var(--border)' }"
      >
        <h3
          class="text-[10px] font-semibold uppercase tracking-wider px-2 pb-1"
          :style="{ color: 'var(--text-tertiary)' }"
        >
          Saga
        </h3>
        <SagaStep
          v-for="(step, idx) in deployment.steps"
          :key="step.id"
          :step="step"
          :index="idx"
        />
      </section>

      <!-- Log stream -->
      <section class="lg:col-span-3 overflow-hidden flex flex-col">
        <div
          class="flex items-center justify-between px-4 py-2 border-b"
          :style="{ borderColor: 'var(--border)' }"
        >
          <h3
            class="text-[10px] font-semibold uppercase tracking-wider"
            :style="{ color: 'var(--text-tertiary)' }"
          >
            Logs ({{ deployment.logs.length }})
          </h3>
          <label class="flex items-center gap-1 text-[10px]" :style="{ color: 'var(--text-tertiary)' }">
            <input v-model="autoFollow" type="checkbox" class="accent-[var(--brand-600)]">
            Auto-scroll
          </label>
        </div>
        <div ref="logContainer" class="flex-1 overflow-y-auto py-2 space-y-0.5">
          <LogLine v-for="log in deployment.logs" :key="log.id" :log="log" />
          <div
            v-if="deployment.logs.length === 0"
            class="text-center text-[11px] py-8"
            :style="{ color: 'var(--text-tertiary)' }"
          >
            Aguardando logs...
          </div>
        </div>
      </section>
    </div>
  </div>
</template>

<script setup lang="ts">
import type { Deployment } from "~/types/deployment"

const props = defineProps<{ deployment: Deployment }>()

const deploymentsStore = useDeploymentsStore()
const pipelinesStore = usePipelinesStore()

const autoFollow = ref(true)
const logContainer = ref<HTMLElement | null>(null)

const completedSteps = computed(() =>
  props.deployment.steps.filter((s) => s.status === "success").length,
)

const progressPercent = computed(() =>
  Math.round((completedSteps.value / props.deployment.steps.length) * 100),
)

const statusLabel = computed(() => {
  const map: Record<string, string> = {
    pending: "Pendente",
    running: "Rodando",
    success: "Concluído",
    failed: "Falhou",
    cancelled: "Cancelado",
  }
  return map[props.deployment.status] ?? props.deployment.status
})

const statusColor = computed<"primary" | "success" | "error" | "warning" | "neutral">(() => {
  switch (props.deployment.status) {
    case "success":
      return "success"
    case "failed":
      return "error"
    case "running":
      return "primary"
    case "cancelled":
      return "warning"
    default:
      return "neutral"
  }
})

const progressTone = computed<"brand" | "success" | "error" | "warning">(() => {
  if (props.deployment.status === "success") return "success"
  if (props.deployment.status === "failed") return "error"
  if (props.deployment.status === "cancelled") return "warning"
  return "brand"
})

function relativeTime(iso: string): string {
  const diff = Date.now() - new Date(iso).getTime()
  const minutes = Math.floor(diff / 60000)
  if (minutes < 1) return "agora"
  if (minutes < 60) return `${minutes}min atrás`
  const hours = Math.floor(minutes / 60)
  if (hours < 24) return `${hours}h atrás`
  const days = Math.floor(hours / 24)
  return `${days}d atrás`
}

function formatDuration(ms: number): string {
  const seconds = Math.floor(ms / 1000)
  if (seconds < 60) return `${seconds}s`
  const minutes = Math.floor(seconds / 60)
  const rem = seconds % 60
  return `${minutes}m ${rem}s`
}

async function openPipelineChat() {
  if (!props.deployment.pipelineId) return
  // Refresca a lista de pipelines pra incluir o novo criado pela saga
  await pipelinesStore.load(true)
  pipelinesStore.setActive(props.deployment.pipelineId)
  navigateTo("/chat")
}

function scrollToBottom() {
  nextTick(() => {
    const el = logContainer.value
    if (el && autoFollow.value) el.scrollTop = el.scrollHeight
  })
}

watch(() => props.deployment.logs.length, scrollToBottom)
onMounted(() => scrollToBottom())
</script>
