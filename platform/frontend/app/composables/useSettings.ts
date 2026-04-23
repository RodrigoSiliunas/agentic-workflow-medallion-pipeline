/**
 * Composable para settings — credenciais + provider/model selection.
 */
interface CompanySettings {
  preferred_model: string
  preferred_provider: string
  credentials: Record<string, { is_configured?: boolean; is_valid?: boolean }>
}

export function useSettings() {
  const api = useApiClient()
  const settings = ref<CompanySettings>({
    preferred_model: "claude-sonnet-4-6",
    preferred_provider: "anthropic",
    credentials: {},
  })
  const loading = ref(false)

  async function load() {
    loading.value = true
    try {
      settings.value = await api.get<CompanySettings>("/settings")
    } catch {
      // silently fail
    } finally {
      loading.value = false
    }
  }

  async function saveCredential(type: string, value: string) {
    await api.put("/settings/credentials", { credential_type: type, value })
    await load()
  }

  async function testCredential(
    type: string,
  ): Promise<{ success: boolean; message?: string; error?: string }> {
    return api.post(`/settings/credentials/${type}/test`)
  }

  async function updateModel(model: string) {
    await api.put("/settings/preferred-model", { model })
    settings.value.preferred_model = model
  }

  async function updateProvider(provider: string) {
    await api.put("/settings/preferred-provider", { provider })
    settings.value.preferred_provider = provider
  }

  onMounted(load)

  return {
    settings,
    loading,
    load,
    saveCredential,
    testCredential,
    updateModel,
    updateProvider,
  }
}
