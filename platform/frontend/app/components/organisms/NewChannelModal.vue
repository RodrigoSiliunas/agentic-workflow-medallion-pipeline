<template>
  <div
    v-if="open"
    class="fixed inset-0 z-50 flex items-center justify-center p-4"
    :style="{ background: 'rgba(0,0,0,0.6)' }"
    @click.self="close"
  >
    <div
      class="w-full max-w-md rounded-[var(--radius-xl)] border border-[var(--border)] bg-[var(--surface)] p-6 shadow-[var(--shadow-medium)]"
    >
      <div class="flex items-start justify-between mb-4">
        <div>
          <h2 class="text-base font-semibold tracking-tight" :style="{ color: 'var(--text-primary)' }">
            Nova instância
          </h2>
          <p class="text-xs mt-1" :style="{ color: 'var(--text-secondary)' }">
            Escolha o canal e dê um nome. Você pareia em seguida.
          </p>
        </div>
        <AppButton variant="ghost" size="sm" icon="i-heroicons-x-mark" square @click="close" />
      </div>

      <div class="mb-4">
        <label
          class="block text-xs font-medium mb-2"
          :style="{ color: 'var(--text-secondary)' }"
        >
          Canal
        </label>
        <div class="grid grid-cols-3 gap-2">
          <button
            v-for="opt in channelOptions"
            :key="opt.value"
            type="button"
            class="flex flex-col items-center gap-1 p-3 rounded-[var(--radius-md)] border transition-colors"
            :style="channelStyle(opt.value)"
            @click="selectedChannel = opt.value"
          >
            <ChannelIcon :channel="opt.value" size="md" />
            <span class="text-[11px] font-medium capitalize">{{ opt.label }}</span>
          </button>
        </div>
      </div>

      <AppInput
        v-model="name"
        label="Nome da instância"
        placeholder="safatechx-suporte"
        helper="Mínimo 2 caracteres. Vai virar parte do identificador no Omni."
      />

      <p
        v-if="error"
        class="mt-3 text-[11px]"
        :style="{ color: 'var(--status-error)' }"
      >
        {{ error }}
      </p>

      <div class="flex items-center justify-end gap-2 mt-6">
        <AppButton variant="ghost" size="sm" @click="close">Cancelar</AppButton>
        <AppButton
          size="sm"
          :loading="creating"
          :disabled="!canCreate"
          icon="i-heroicons-plus"
          @click="handleCreate"
        >
          Criar
        </AppButton>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import type { ChannelKind } from "~/types/channel"

const props = defineProps<{ open: boolean }>()
const emit = defineEmits<{
  close: []
  created: [id: string, channel: ChannelKind]
}>()

const channelsStore = useChannelsStore()

const channelOptions: Array<{ value: ChannelKind; label: string }> = [
  { value: "whatsapp", label: "WhatsApp" },
  { value: "discord", label: "Discord" },
  { value: "telegram", label: "Telegram" },
]

const selectedChannel = ref<ChannelKind>("whatsapp")
const name = ref("")
const error = ref("")
const creating = ref(false)

const canCreate = computed(() => name.value.trim().length >= 2 && !creating.value)

function channelStyle(channel: ChannelKind): Record<string, string> {
  const active = selectedChannel.value === channel
  return {
    background: active ? "var(--brand-600)" : "var(--surface-elevated)",
    color: active ? "white" : "var(--text-secondary)",
    borderColor: active ? "var(--brand-600)" : "var(--border)",
  }
}

function close() {
  if (creating.value) return
  error.value = ""
  name.value = ""
  selectedChannel.value = "whatsapp"
  emit("close")
}

async function handleCreate() {
  error.value = ""
  creating.value = true
  try {
    const instance = await channelsStore.create(name.value.trim(), selectedChannel.value)
    emit("created", instance.id, selectedChannel.value)
    close()
  } catch (e: unknown) {
    error.value = e instanceof Error ? e.message : "Falha ao criar instância"
  } finally {
    creating.value = false
  }
}

// Fecha modal se o prop open mudar para false externamente
watch(
  () => props.open,
  (val) => {
    if (!val) {
      error.value = ""
      creating.value = false
    }
  },
)
</script>
