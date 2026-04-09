/**
 * Composable para pipelines — lista, status, polling.
 */
import type { Pipeline } from "~/types/pipeline"

export function usePipelines() {
  const api = useApiClient()
  const pipelines = ref<Pipeline[]>([])
  const loading = ref(false)

  async function load() {
    loading.value = true
    try {
      pipelines.value = await api.get<Pipeline[]>("/pipelines")
    } catch {
      pipelines.value = []
    } finally {
      loading.value = false
    }
  }

  // Polling a cada 30s
  let interval: ReturnType<typeof setInterval> | null = null

  function startPolling() {
    load()
    interval = setInterval(load, 30_000)
  }

  function stopPolling() {
    if (interval) clearInterval(interval)
  }

  onMounted(startPolling)
  onUnmounted(stopPolling)

  return { pipelines, loading, load }
}
