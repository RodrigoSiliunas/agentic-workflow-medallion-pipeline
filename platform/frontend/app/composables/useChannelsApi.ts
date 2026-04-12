/**
 * API client wrapper para /api/v1/channels — gerenciamento de instancias Omni.
 * Single decision point para mock vs real — stores nunca fazem branching.
 */
import type { ChannelKind, OmniInstance, QRCodeInfo } from "~/types/channel"
import {
  MOCK_INSTANCES,
  connectMockInstance,
  createMockInstance,
  getMockQrCode,
} from "~/composables/mock/channels"

interface OmniInstanceDTO {
  id: string
  omni_instance_id: string | null
  name: string
  channel: ChannelKind
  state: OmniInstance["state"]
  last_sync_at: string | null
  last_error: string | null
  created_at: string
  updated_at: string
}

interface QRCodeDTO {
  instance_id: string
  state: OmniInstance["state"]
  qr_code: string | null
  expires_at: string | null
}

function fromApi(dto: OmniInstanceDTO): OmniInstance {
  return {
    id: dto.id,
    omniInstanceId: dto.omni_instance_id,
    name: dto.name,
    channel: dto.channel,
    state: dto.state,
    lastSyncAt: dto.last_sync_at,
    lastError: dto.last_error,
    createdAt: dto.created_at,
    updatedAt: dto.updated_at,
  }
}

function qrFromApi(dto: QRCodeDTO): QRCodeInfo {
  return {
    instanceId: dto.instance_id,
    state: dto.state,
    qrCode: dto.qr_code,
    expiresAt: dto.expires_at,
  }
}

export function useChannelsApi() {
  const api = useApiClient()
  const isMock = Boolean(useRuntimeConfig().public.mockMode)

  // Cache local de instancias mock para operacoes de mutacao
  let _mockInstances: OmniInstance[] | null = null
  function getMockInstances(): OmniInstance[] {
    if (!_mockInstances) _mockInstances = structuredClone(MOCK_INSTANCES)
    return _mockInstances
  }

  async function list(): Promise<OmniInstance[]> {
    if (isMock) return structuredClone(getMockInstances())
    const data = await api.get<OmniInstanceDTO[]>("/channels")
    return data.map(fromApi)
  }

  async function create(name: string, channel: ChannelKind): Promise<OmniInstance> {
    if (isMock) {
      const mock = createMockInstance(name, channel)
      getMockInstances().unshift(mock)
      return mock
    }
    const data = await api.post<OmniInstanceDTO>("/channels", { name, channel })
    return fromApi(data)
  }

  async function connect(id: string, token?: string): Promise<OmniInstance> {
    if (isMock) {
      const instances = getMockInstances()
      const instance = instances.find((i) => i.id === id)
      if (!instance) throw new Error(`Instance ${id} not found`)
      const updated = connectMockInstance(instance)
      const idx = instances.findIndex((i) => i.id === id)
      if (idx >= 0) instances[idx] = updated
      return updated
    }
    const data = await api.post<OmniInstanceDTO>(`/channels/${id}/connect`, {
      token: token ?? null,
    })
    return fromApi(data)
  }

  async function getQrCode(id: string): Promise<QRCodeInfo> {
    if (isMock) {
      const instance = getMockInstances().find((i) => i.id === id)
      if (!instance) throw new Error(`Instance ${id} not found`)
      return getMockQrCode(instance)
    }
    const data = await api.get<QRCodeDTO>(`/channels/${id}/qr`)
    return qrFromApi(data)
  }

  async function disconnect(id: string): Promise<void> {
    if (isMock) {
      const instances = getMockInstances()
      const instance = instances.find((i) => i.id === id)
      if (instance) instance.state = "disconnected"
      return
    }
    await api.delete(`/channels/${id}`)
  }

  return { list, create, connect, getQrCode, disconnect }
}
