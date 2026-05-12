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
            Conectar {{ channelLabel }}
          </h2>
          <p class="text-xs mt-1" :style="{ color: 'var(--text-secondary)' }">
            {{ instructions }}
          </p>
        </div>
        <AppButton variant="ghost" size="sm" icon="i-heroicons-x-mark" square @click="close" />
      </div>

      <AppInput
        v-model="token"
        label="Bot Token"
        :placeholder="placeholder"
        type="password"
      />

      <p
        v-if="hasSavedToken"
        class="mt-2 text-[11px] flex items-start gap-1"
        :style="{ color: 'var(--text-secondary)' }"
      >
        <AppIcon name="information-circle" size="xs" />
        Token salvo em Settings disponivel. Deixe vazio pra reusar ou cole
        um novo aqui pra sobrescrever so desta vez.
      </p>

      <p
        v-if="error"
        class="mt-3 text-[11px]"
        :style="{ color: 'var(--status-error)' }"
      >
        {{ error }}
      </p>

      <p
        v-if="success"
        class="mt-3 text-[11px] flex items-center gap-1"
        :style="{ color: 'var(--status-success)' }"
      >
        <AppIcon name="check-circle" size="xs" />
        Conectado com sucesso!
      </p>

      <div class="flex items-center justify-end gap-2 mt-6">
        <AppButton variant="ghost" size="sm" @click="close">
          {{ success ? 'Fechar' : 'Cancelar' }}
        </AppButton>
        <AppButton
          v-if="!success"
          size="sm"
          :loading="connecting"
          :disabled="!token.trim() && !hasSavedToken"
          icon="i-heroicons-link"
          @click="handleConnect"
        >
          {{ !token.trim() && hasSavedToken ? "Usar token salvo" : "Conectar" }}
        </AppButton>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import type { ChannelKind } from "~/types/channel"

const props = defineProps<{
  instanceId: string | null
  channel: ChannelKind
}>()

const emit = defineEmits<{ close: [] }>()

const channelsStore = useChannelsStore()
const { settings, load: loadSettings } = useSettings()

const token = ref("")
const error = ref("")
const connecting = ref(false)
const success = ref(false)

const credentialType = computed(() => `${props.channel}_bot_token`)
const hasSavedToken = computed(
  () => Boolean(settings.value.credentials[credentialType.value]?.is_configured),
)

const channelLabel = computed(() => {
  const labels: Record<string, string> = { discord: "Discord", telegram: "Telegram" }
  return labels[props.channel] || props.channel
})

const instructions = computed(() => {
  if (props.channel === "telegram") {
    return "Cole o token do @BotFather. Formato: 1234567890:ABCdef..."
  }
  return "Cole o token do bot criado no Discord Developer Portal."
})

const placeholder = computed(() => {
  if (props.channel === "telegram") return "1234567890:ABCdefGHIjklMNO..."
  return "MTIzNDU2Nzg5MDEy..."
})

function close() {
  if (connecting.value) return
  token.value = ""
  error.value = ""
  success.value = false
  emit("close")
}

async function handleConnect() {
  if (!props.instanceId) return
  const trimmed = token.value.trim()
  // Sem token e sem credential salva = nada pra mandar.
  if (!trimmed && !hasSavedToken.value) return
  error.value = ""
  connecting.value = true
  try {
    // Token vazio com credential salva = backend faz fallback.
    await channelsStore.connect(props.instanceId, trimmed || undefined)
    success.value = true
  } catch (e: unknown) {
    error.value = e instanceof Error ? e.message : "Falha ao conectar"
  } finally {
    connecting.value = false
  }
}

watch(
  () => props.instanceId,
  async (id) => {
    if (id) {
      token.value = ""
      error.value = ""
      success.value = false
      // Buscar status das credentials pra decidir hint + button label.
      await loadSettings()
    }
  },
)
</script>
