<template>
  <div
    class="rounded-[var(--radius-lg)] border border-[var(--border)] bg-[var(--surface)] p-5 flex flex-col"
  >
    <div class="flex items-start gap-3 mb-3">
      <div
        class="w-11 h-11 rounded-[var(--radius-md)] flex items-center justify-center flex-shrink-0"
        :style="{ background: iconBg }"
      >
        <ChannelIcon :channel="instance.channel" size="md" />
      </div>
      <div class="flex-1 min-w-0">
        <h3 class="text-sm font-semibold truncate" :style="{ color: 'var(--text-primary)' }">
          {{ instance.name }}
        </h3>
        <p class="text-[11px] truncate capitalize" :style="{ color: 'var(--text-tertiary)' }">
          {{ instance.channel }}
        </p>
      </div>
      <AppBadge :color="stateColor" variant="subtle">{{ stateLabel }}</AppBadge>
    </div>

    <dl class="space-y-1.5 mb-4 text-[11px]">
      <div class="flex justify-between">
        <dt :style="{ color: 'var(--text-tertiary)' }">Ultimo sync</dt>
        <dd :style="{ color: 'var(--text-secondary)' }">{{ lastSyncLabel }}</dd>
      </div>
      <div class="flex justify-between">
        <dt :style="{ color: 'var(--text-tertiary)' }">Instância</dt>
        <dd
          class="font-[var(--font-mono)] truncate max-w-[180px]"
          :style="{ color: 'var(--text-secondary)' }"
        >
          {{ instance.omniInstanceId ?? "—" }}
        </dd>
      </div>
    </dl>

    <p
      v-if="instance.lastError"
      class="mb-3 text-[11px] p-2 rounded-[var(--radius-sm)] border border-[var(--status-error)]/30 bg-[var(--status-error)]/10"
      :style="{ color: 'var(--status-error)' }"
    >
      {{ instance.lastError }}
    </p>

    <div class="flex items-center gap-2 mt-auto pt-3 border-t" :style="{ borderColor: 'var(--border)' }">
      <AppButton
        v-if="instance.channel === 'whatsapp' && instance.state !== 'connected'"
        size="sm"
        variant="outline"
        icon="i-heroicons-qr-code"
        @click="$emit('pair', instance.id)"
      >
        QR Pair
      </AppButton>
      <AppButton
        v-if="instance.channel !== 'whatsapp' && instance.state !== 'connected'"
        size="sm"
        variant="outline"
        icon="i-heroicons-link"
        @click="$emit('connect', instance.id)"
      >
        Connect
      </AppButton>
      <AppButton
        v-if="instance.state === 'connected'"
        size="sm"
        variant="ghost"
        icon="i-heroicons-arrow-path"
        @click="$emit('resync', instance.id)"
      >
        Ressincronizar
      </AppButton>
      <AppButton
        size="sm"
        variant="ghost"
        icon="i-heroicons-trash"
        class="ml-auto"
        @click="$emit('disconnect', instance.id)"
      >
        Remover
      </AppButton>
    </div>
  </div>
</template>

<script setup lang="ts">
import type { OmniInstance } from "~/types/channel"

const props = defineProps<{ instance: OmniInstance }>()

defineEmits<{
  pair: [id: string]
  connect: [id: string]
  disconnect: [id: string]
  resync: [id: string]
}>()

const CHANNEL_BG: Record<string, string> = {
  whatsapp: "#25d366",
  discord: "#5865f2",
  telegram: "#229ed9",
}

const iconBg = computed(() => CHANNEL_BG[props.instance.channel] ?? "var(--brand-600)")

const STATE_LABELS: Record<OmniInstance["state"], string> = {
  connecting: "Conectando",
  connected: "Conectado",
  disconnected: "Desconectado",
  failed: "Falhou",
}
const stateLabel = computed(() => STATE_LABELS[props.instance.state])

const STATE_COLORS: Record<
  OmniInstance["state"],
  "primary" | "success" | "warning" | "error" | "neutral"
> = {
  connecting: "warning",
  connected: "success",
  disconnected: "neutral",
  failed: "error",
}
const stateColor = computed(() => STATE_COLORS[props.instance.state])

const lastSyncLabel = computed(() => {
  if (!props.instance.lastSyncAt) return "Nunca"
  const diff = Date.now() - new Date(props.instance.lastSyncAt).getTime()
  const minutes = Math.floor(diff / 60000)
  if (minutes < 1) return "agora"
  if (minutes < 60) return `${minutes}min atrás`
  const hours = Math.floor(minutes / 60)
  if (hours < 24) return `${hours}h atrás`
  const days = Math.floor(hours / 24)
  return `${days}d atrás`
})
</script>
