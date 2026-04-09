/**
 * Composable para settings — credenciais + model selection.
 */
export function useSettings() {
  const api = useApiClient()
  const settings = ref<{ preferred_model: string; credentials: Record<string, any> }>({
    preferred_model: "sonnet",
    credentials: {},
  })
  const loading = ref(false)

  async function load() {
    loading.value = true
    try {
      settings.value = await api.get("/settings")
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

  async function testCredential(type: string): Promise<{ success: boolean; message?: string; error?: string }> {
    return api.post(`/settings/credentials/${type}/test`)
  }

  async function updateModel(model: string) {
    await api.put("/settings/preferred-model", { model })
    settings.value.preferred_model = model
  }

  onMounted(load)

  return { settings, loading, load, saveCredential, testCredential, updateModel }
}
