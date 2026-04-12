export type ChannelKind = "whatsapp" | "discord" | "telegram"

export type OmniInstanceState = "connecting" | "connected" | "disconnected" | "failed"

export interface OmniInstance {
  id: string
  omniInstanceId: string | null
  name: string
  channel: ChannelKind
  state: OmniInstanceState
  lastSyncAt: string | null
  lastError: string | null
  createdAt: string
  updatedAt: string
}

export interface QRCodeInfo {
  instanceId: string
  state: OmniInstanceState
  qrCode: string | null
  expiresAt: string | null
}
