<template>
  <div
    v-if="instanceId"
    class="fixed inset-0 z-50 flex items-center justify-center p-4"
    :style="{ background: 'rgba(0,0,0,0.6)' }"
    @click.self="close"
  >
    <div
      class="w-full max-w-sm rounded-[var(--radius-xl)] border border-[var(--border)] bg-[var(--surface)] p-6 shadow-[var(--shadow-medium)]"
    >
      <div class="flex items-start justify-between mb-4">
        <div>
          <h2 class="text-base font-semibold tracking-tight" :style="{ color: 'var(--text-primary)' }">
            Parear WhatsApp
          </h2>
          <p class="text-xs mt-1" :style="{ color: 'var(--text-secondary)' }">
            Escaneie o QR no seu celular: menu → Aparelhos conectados.
          </p>
        </div>
        <AppButton variant="ghost" size="sm" icon="i-heroicons-x-mark" square @click="close" />
      </div>

      <div
        class="aspect-square w-full rounded-[var(--radius-lg)] border border-[var(--border)] bg-[var(--surface-elevated)] flex items-center justify-center mb-4 overflow-hidden"
      >
        <div v-if="loading" class="text-center">
          <AppIcon name="arrow-path" size="xl" class="animate-spin text-[var(--brand-500)]" />
          <p class="mt-2 text-[11px]" :style="{ color: 'var(--text-tertiary)' }">
            Buscando QR code...
          </p>
        </div>
        <div v-else-if="connected" class="text-center">
          <AppIcon name="check-circle" size="xl" class="text-[var(--status-success)]" />
          <p class="mt-2 text-sm font-medium" :style="{ color: 'var(--text-primary)' }">
            Conectado!
          </p>
        </div>
        <img
          v-else-if="qrImageSrc"
          :src="qrImageSrc"
          alt="QR Code"
          class="w-full h-full object-contain p-4"
        >
        <div v-else class="text-center p-4">
          <AppIcon name="qr-code" size="xl" class="text-[var(--text-tertiary)]" />
          <p class="mt-2 text-[11px]" :style="{ color: 'var(--text-tertiary)' }">
            {{ error || "Aguardando QR code do Omni..." }}
          </p>
        </div>
      </div>

      <div
        class="flex items-center gap-2 text-[11px] justify-center mb-4"
        :style="{ color: 'var(--text-tertiary)' }"
      >
        <span
          class="inline-block w-1.5 h-1.5 rounded-full"
          :class="{ 'status-pulse': !connected }"
          :style="{ background: connected ? 'var(--status-success)' : 'var(--status-warning)' }"
        />
        <span>{{ statusLabel }}</span>
      </div>

      <AppButton
        v-if="connected"
        size="sm"
        class="w-full justify-center"
        @click="close"
      >
        Concluir
      </AppButton>
      <AppButton
        v-else
        variant="outline"
        size="sm"
        class="w-full justify-center"
        icon="i-heroicons-arrow-path"
        :loading="loading"
        @click="fetchQr"
      >
        Atualizar QR
      </AppButton>
    </div>
  </div>
</template>

<script setup lang="ts">
const props = defineProps<{
  instanceId: string | null
}>()

const emit = defineEmits<{ close: [] }>()

const channelsStore = useChannelsStore()

const qrCode = ref<string | null>(null)
const loading = ref(false)
const error = ref("")
const connected = ref(false)

let pollTimer: ReturnType<typeof setInterval> | null = null

const qrImageSrc = computed(() => {
  if (!qrCode.value) return null
  // Se ja e um data URL ou URL normal, usa direto
  if (qrCode.value.startsWith("data:") || qrCode.value.startsWith("http")) {
    return qrCode.value
  }
  // Se e o mock, gera um placeholder SVG leve
  if (qrCode.value === "MOCK_QR_CODE_DATA_FAKE") {
    return buildMockQrSvg()
  }
  // Assume base64 puro
  return `data:image/png;base64,${qrCode.value}`
})

const statusLabel = computed(() => {
  if (connected.value) return "Conectado com sucesso"
  if (loading.value) return "Buscando..."
  if (qrCode.value) return "Aguardando scan"
  return "Pendente"
})

function buildMockQrSvg(): string {
  // Placeholder visual: pattern xadrez pra simular um QR em dev offline
  const svg = `<svg xmlns='http://www.w3.org/2000/svg' width='240' height='240' viewBox='0 0 24 24'>
    <rect width='24' height='24' fill='white'/>
    ${Array.from({ length: 144 }, (_, i) => {
      const x = i % 12
      const y = Math.floor(i / 12)
      return (x + y) % 2 === 0 && Math.random() > 0.3
        ? `<rect x='${x * 2}' y='${y * 2}' width='2' height='2' fill='black'/>`
        : ""
    }).join("")}
  </svg>`
  return `data:image/svg+xml;base64,${btoa(svg)}`
}

async function fetchQr() {
  if (!props.instanceId) return
  loading.value = true
  error.value = ""
  try {
    const info = await channelsStore.getQrCode(props.instanceId)
    if (!info) {
      error.value = "Instância não encontrada"
      return
    }
    qrCode.value = info.qrCode
    if (info.state === "connected") {
      connected.value = true
      stopPolling()
    }
  } catch (e: unknown) {
    error.value = e instanceof Error ? e.message : "Falha ao buscar QR"
  } finally {
    loading.value = false
  }
}

function startPolling() {
  stopPolling()
  pollTimer = setInterval(fetchQr, 3000)
}

function stopPolling() {
  if (pollTimer) {
    clearInterval(pollTimer)
    pollTimer = null
  }
}

function close() {
  stopPolling()
  qrCode.value = null
  connected.value = false
  error.value = ""
  emit("close")
}

watch(
  () => props.instanceId,
  (id) => {
    if (id) {
      connected.value = false
      qrCode.value = null
      fetchQr()
      startPolling()
    } else {
      stopPolling()
    }
  },
  { immediate: true },
)

onUnmounted(() => stopPolling())
</script>
