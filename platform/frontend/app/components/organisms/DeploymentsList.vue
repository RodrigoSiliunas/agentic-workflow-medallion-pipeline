<template>
  <div class="flex-1 overflow-y-auto">
    <div class="max-w-5xl mx-auto px-8 py-8">
      <header class="mb-6">
        <h1 class="text-2xl font-semibold tracking-tight mb-1" :style="{ color: 'var(--text-primary)' }">
          Deployments
        </h1>
        <p class="text-sm" :style="{ color: 'var(--text-secondary)' }">
          Histórico de todos os deploys one-click executados pela sua conta.
        </p>
      </header>

      <EmptyState
        v-if="deployments.length === 0"
        icon="rocket-launch"
        title="Nenhum deployment ainda"
        description="Escolha um template no marketplace para executar seu primeiro deploy."
      >
        <AppButton to="/marketplace" icon="i-heroicons-squares-2x2">
          Ver marketplace
        </AppButton>
      </EmptyState>

      <div
        v-else
        class="rounded-[var(--radius-lg)] border border-[var(--border)] bg-[var(--surface)] overflow-hidden"
      >
        <div
          class="grid grid-cols-[1fr_auto_auto_auto_auto] gap-4 px-5 py-3 border-b text-[10px] uppercase tracking-wider font-semibold"
          :style="{ borderColor: 'var(--border)', color: 'var(--text-tertiary)' }"
        >
          <span>Nome</span>
          <span class="hidden sm:inline">Env</span>
          <span class="hidden md:inline">Duração</span>
          <span class="hidden md:inline">Criado</span>
          <span>Status</span>
        </div>
        <NuxtLink
          v-for="d in deployments"
          :key="d.id"
          :to="`/deployments/${d.id}`"
          class="grid grid-cols-[1fr_auto_auto_auto_auto] gap-4 px-5 py-3 items-center border-b last:border-b-0 hover:bg-[var(--surface-elevated)] transition-colors"
          :style="{ borderColor: 'var(--border)' }"
        >
          <div class="min-w-0">
            <p class="text-sm font-medium truncate" :style="{ color: 'var(--text-primary)' }">
              {{ d.config.name }}
            </p>
            <p class="text-[11px] truncate" :style="{ color: 'var(--text-tertiary)' }">
              {{ d.templateName }}
            </p>
          </div>
          <span
            class="hidden sm:inline text-[11px] font-medium uppercase tracking-wider"
            :style="{ color: 'var(--text-secondary)' }"
          >
            {{ d.config.environment }}
          </span>
          <span
            class="hidden md:inline text-[11px] tabular-nums"
            :style="{ color: 'var(--text-tertiary)' }"
          >
            {{ d.durationMs ? formatDuration(d.durationMs) : "—" }}
          </span>
          <span
            class="hidden md:inline text-[11px]"
            :style="{ color: 'var(--text-tertiary)' }"
          >
            {{ relativeTime(d.createdAt) }}
          </span>
          <AppBadge :color="statusColorFor(d.status)" variant="subtle">
            {{ statusLabelFor(d.status) }}
          </AppBadge>
        </NuxtLink>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import type { DeploymentStatus } from "~/types/deployment"

const store = useDeploymentsStore()
const deployments = computed(() => store.list)

function statusLabelFor(status: DeploymentStatus): string {
  const map: Record<DeploymentStatus, string> = {
    pending: "Pendente",
    running: "Rodando",
    success: "Sucesso",
    failed: "Falhou",
    cancelled: "Cancelado",
  }
  return map[status]
}

function statusColorFor(
  status: DeploymentStatus,
): "primary" | "success" | "error" | "warning" | "neutral" {
  switch (status) {
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
}

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
</script>
