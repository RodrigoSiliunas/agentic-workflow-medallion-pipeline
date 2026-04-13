<template>
  <div class="flex-1 flex flex-col overflow-hidden">
    <header
      class="px-6 pt-6 pb-4 border-b"
      :style="{ borderColor: 'var(--border)' }"
    >
      <div class="flex items-start justify-between gap-4">
        <div>
          <h1
            class="text-2xl font-semibold tracking-tight mb-1"
            :style="{ color: 'var(--text-primary)' }"
          >
            Channels
          </h1>
          <p class="text-sm" :style="{ color: 'var(--text-secondary)' }">
            Gerencie instâncias Omni (WhatsApp, Discord, Telegram) vinculadas aos seus pipelines.
          </p>
        </div>
        <AppButton icon="i-heroicons-plus" size="md" @click="openNewModal = true">
          Nova instância
        </AppButton>
      </div>

      <div
        v-if="store.omniHealthy === false"
        class="mt-4 px-3 py-2 rounded-[var(--radius-md)] border border-[var(--status-warning)]/40 bg-[var(--status-warning)]/10 text-[11px] flex items-center gap-2"
        :style="{ color: 'var(--status-warning)' }"
      >
        <AppIcon name="exclamation-triangle" size="xs" />
        Omni gateway indisponível — algumas operações podem falhar.
      </div>
    </header>

    <div class="flex-1 overflow-y-auto px-6 py-6">
      <div
        v-if="active.length > 0"
        class="grid gap-4 grid-cols-1 md:grid-cols-2 xl:grid-cols-3"
      >
        <ChannelCard
          v-for="instance in active"
          :key="instance.id"
          :instance="instance"
          @pair="onPair"
          @connect="onConnect"
          @disconnect="onDisconnect"
          @resync="onResync"
        />
      </div>
      <EmptyState
        v-else
        icon="phone"
        title="Sem canais conectados"
        description="Adicione uma instância WhatsApp, Discord ou Telegram para começar a receber mensagens no chat."
      >
        <AppButton icon="i-heroicons-plus" @click="openNewModal = true">
          Conectar primeiro canal
        </AppButton>
      </EmptyState>
    </div>

    <NewChannelModal
      :open="openNewModal"
      @close="openNewModal = false"
      @created="onCreated"
    />

    <QrPairingModal :instance-id="pairingInstanceId" @close="onPairingClosed" />

    <TokenInputModal
      :instance-id="tokenInstanceId"
      :channel="tokenChannel"
      @close="onTokenClosed"
    />
  </div>
</template>

<script setup lang="ts">
import type { ChannelKind, OmniInstance } from "~/types/channel"

definePageMeta({ layout: "default" })

const route = useRoute()
const store = useChannelsStore()
await store.load()

const openNewModal = ref(route.query.new === "1")
const pairingInstanceId = ref<string | null>(null)
const tokenInstanceId = ref<string | null>(null)
const tokenChannel = ref<ChannelKind>("telegram")

watch(openNewModal, (val) => {
  if (!val && route.query.new === "1") {
    navigateTo({ path: "/channels" }, { replace: true })
  }
})

const active = computed<OmniInstance[]>(() =>
  store.instances.filter((i) => i.state !== "disconnected"),
)

function onCreated(id: string, channel: ChannelKind) {
  if (channel === "whatsapp") {
    pairingInstanceId.value = id
  } else {
    // Discord/Telegram — abrir modal de token direto
    tokenInstanceId.value = id
    tokenChannel.value = channel
  }
}

function onPair(id: string) {
  pairingInstanceId.value = id
}

function onConnect(id: string) {
  const instance = store.getById(id)
  if (!instance) return
  tokenInstanceId.value = id
  tokenChannel.value = instance.channel
}

async function onDisconnect(id: string) {
  const instance = store.getById(id)
  if (!instance) return
  if (!confirm(`Desconectar ${instance.name}?`)) return
  await store.disconnect(id)
}

async function onPairingClosed() {
  pairingInstanceId.value = null
  await store.load(true)
}

async function onTokenClosed() {
  tokenInstanceId.value = null
  await store.load(true)
}

async function onResync(id: string) {
  await store.load(true)
  const instance = store.getById(id)
  if (!instance) return
  if (instance.channel === "whatsapp" && instance.state !== "connected") {
    pairingInstanceId.value = id
  } else if (instance.state !== "connected") {
    tokenInstanceId.value = id
    tokenChannel.value = instance.channel
  }
}
</script>
