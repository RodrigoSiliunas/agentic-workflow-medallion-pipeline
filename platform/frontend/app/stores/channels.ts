/**
 * Channels store — gerencia instancias Omni: WhatsApp, Discord, Telegram.
 * Mock branching foi movido para useChannelsApi (Strategy pattern).
 */
import { defineStore } from "pinia"
import type { ChannelKind, OmniInstance, QRCodeInfo } from "~/types/channel"

export const useChannelsStore = defineStore("channels", () => {
  const instances = ref<OmniInstance[]>([])
  const loaded = ref(false)
  const loading = ref(false)
  const omniHealthy = ref<boolean | null>(null)

  async function load(force = false) {
    if (loaded.value && !force) return
    loading.value = true
    try {
      const api = useChannelsApi()
      instances.value = await api.list()
      loaded.value = true
      omniHealthy.value = true
    } catch (e) {
      console.error("Failed to load channels", e)
      instances.value = []
      loaded.value = true
      omniHealthy.value = false
    } finally {
      loading.value = false
    }
  }

  function getById(id: string): OmniInstance | undefined {
    return instances.value.find((i) => i.id === id)
  }

  async function create(name: string, channel: ChannelKind): Promise<OmniInstance> {
    const api = useChannelsApi()
    const created = await api.create(name, channel)
    instances.value.unshift(created)
    return created
  }

  async function connect(id: string, token?: string): Promise<void> {
    const api = useChannelsApi()
    const updated = await api.connect(id, token)
    const idx = instances.value.findIndex((i) => i.id === id)
    if (idx >= 0) instances.value[idx] = updated
  }

  async function getQrCode(id: string): Promise<QRCodeInfo | null> {
    const instance = getById(id)
    if (!instance) return null
    const api = useChannelsApi()
    const info = await api.getQrCode(id)
    // Atualizar estado local quando Omni reporta conexao
    if (info.state === "connected" && instance.state !== "connected") {
      instance.state = "connected"
      instance.lastSyncAt = new Date().toISOString()
    }
    return info
  }

  async function disconnect(id: string): Promise<void> {
    const api = useChannelsApi()
    await api.disconnect(id)
    const instance = getById(id)
    if (instance) {
      instance.state = "disconnected"
      instance.lastSyncAt = new Date().toISOString()
    }
  }

  return {
    instances,
    loaded,
    loading,
    omniHealthy,
    load,
    getById,
    create,
    connect,
    getQrCode,
    disconnect,
  }
})
