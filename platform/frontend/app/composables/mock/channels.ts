/**
 * Mock data para channels — usado pelo composable useChannelsApi
 * quando mockMode esta ativo.
 */
import type { ChannelKind, OmniInstance, QRCodeInfo } from "~/types/channel"

export const MOCK_INSTANCES: OmniInstance[] = [
  {
    id: "ch-mock-1",
    omniInstanceId: "omni-wa-acme-1",
    name: "flowertex-suporte",
    channel: "whatsapp",
    state: "connected",
    lastSyncAt: new Date(Date.now() - 1000 * 60 * 3).toISOString(),
    lastError: null,
    createdAt: new Date(Date.now() - 1000 * 60 * 60 * 24 * 4).toISOString(),
    updatedAt: new Date(Date.now() - 1000 * 60 * 3).toISOString(),
  },
  {
    id: "ch-mock-2",
    omniInstanceId: "omni-dc-acme-1",
    name: "flowertex-discord-bot",
    channel: "discord",
    state: "connected",
    lastSyncAt: new Date(Date.now() - 1000 * 60 * 12).toISOString(),
    lastError: null,
    createdAt: new Date(Date.now() - 1000 * 60 * 60 * 24 * 10).toISOString(),
    updatedAt: new Date(Date.now() - 1000 * 60 * 12).toISOString(),
  },
  {
    id: "ch-mock-3",
    omniInstanceId: "omni-tg-acme-1",
    name: "flowertex-telegram-alerts",
    channel: "telegram",
    state: "connecting",
    lastSyncAt: null,
    lastError: null,
    createdAt: new Date(Date.now() - 1000 * 60 * 3).toISOString(),
    updatedAt: new Date(Date.now() - 1000 * 60 * 3).toISOString(),
  },
]

export function createMockInstance(name: string, channel: ChannelKind): OmniInstance {
  return {
    id: `ch-${Math.random().toString(36).slice(2, 10)}`,
    omniInstanceId: `omni-${channel}-${Math.random().toString(36).slice(2, 8)}`,
    name,
    channel,
    state: "connecting",
    lastSyncAt: null,
    lastError: null,
    createdAt: new Date().toISOString(),
    updatedAt: new Date().toISOString(),
  }
}

export function connectMockInstance(instance: OmniInstance): OmniInstance {
  return {
    ...instance,
    state: "connected",
    lastSyncAt: new Date().toISOString(),
    updatedAt: new Date().toISOString(),
  }
}

export function getMockQrCode(instance: OmniInstance): QRCodeInfo {
  return {
    instanceId: instance.id,
    state: instance.state,
    qrCode: "MOCK_QR_CODE_DATA_FAKE",
    expiresAt: null,
  }
}
