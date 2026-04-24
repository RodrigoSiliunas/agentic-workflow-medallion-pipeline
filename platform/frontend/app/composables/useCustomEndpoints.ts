/**
 * Composable pra custom LLM endpoints (Ollama, vLLM, OpenRouter, etc).
 *
 * CRUD + test connection + auto-discovery de models.
 */

export interface CustomLLMModelInfo {
  id: string
  label?: string
}

export interface CustomLLMEndpoint {
  id: string
  name: string
  base_url: string
  has_api_key: boolean
  models: CustomLLMModelInfo[]
  enabled: boolean
  last_tested_at: string | null
  last_test_status: string | null
  created_at: string
  updated_at: string
}

export interface CreateEndpointPayload {
  name: string
  base_url: string
  api_key?: string
  models?: CustomLLMModelInfo[]
  enabled?: boolean
}

export interface UpdateEndpointPayload {
  name?: string
  base_url?: string
  api_key?: string
  models?: CustomLLMModelInfo[]
  enabled?: boolean
}

export interface TestEndpointResult {
  success: boolean
  error?: string
  discovered_models: CustomLLMModelInfo[]
  server_type?: string
}

export function useCustomEndpoints() {
  const api = useApiClient()
  const endpoints = ref<CustomLLMEndpoint[]>([])
  const loading = ref(false)

  async function load() {
    loading.value = true
    try {
      endpoints.value = await api.get<CustomLLMEndpoint[]>("/llm/endpoints")
    } catch (e) {
      console.error("Failed to load custom endpoints", e)
      endpoints.value = []
    } finally {
      loading.value = false
    }
  }

  async function create(payload: CreateEndpointPayload): Promise<CustomLLMEndpoint> {
    const created = await api.post<CustomLLMEndpoint>("/llm/endpoints", payload)
    endpoints.value.unshift(created)
    return created
  }

  async function update(
    id: string,
    payload: UpdateEndpointPayload,
  ): Promise<CustomLLMEndpoint> {
    const updated = await api.put<CustomLLMEndpoint>(`/llm/endpoints/${id}`, payload)
    const idx = endpoints.value.findIndex((e) => e.id === id)
    if (idx >= 0) endpoints.value[idx] = updated
    return updated
  }

  async function remove(id: string): Promise<void> {
    await api.delete(`/llm/endpoints/${id}`)
    endpoints.value = endpoints.value.filter((e) => e.id !== id)
  }

  async function testConnection(
    base_url: string,
    api_key?: string,
  ): Promise<TestEndpointResult> {
    return api.post<TestEndpointResult>("/llm/endpoints/test", { base_url, api_key })
  }

  async function refreshModels(id: string): Promise<CustomLLMEndpoint> {
    const updated = await api.post<CustomLLMEndpoint>(
      `/llm/endpoints/${id}/refresh-models`,
      {},
    )
    const idx = endpoints.value.findIndex((e) => e.id === id)
    if (idx >= 0) endpoints.value[idx] = updated
    return updated
  }

  return {
    endpoints,
    loading,
    load,
    create,
    update,
    remove,
    testConnection,
    refreshModels,
  }
}
