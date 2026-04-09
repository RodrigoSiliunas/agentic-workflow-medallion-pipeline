/**
 * Composable para threads — CRUD por pipeline.
 */
import type { Thread } from "~/types/chat"

export function useThreads(pipelineId: Ref<string | null>) {
  const api = useApiClient()
  const threads = ref<Thread[]>([])
  const loading = ref(false)

  async function load() {
    if (!pipelineId.value) {
      threads.value = []
      return
    }
    loading.value = true
    try {
      threads.value = await api.get<Thread[]>("/chat/threads", {
        pipeline_id: pipelineId.value,
      })
    } catch {
      threads.value = []
    } finally {
      loading.value = false
    }
  }

  async function create(): Promise<Thread | null> {
    if (!pipelineId.value) return null
    try {
      const thread = await api.post<Thread>("/chat/threads", {
        pipeline_id: pipelineId.value,
      })
      await load()
      return thread
    } catch {
      return null
    }
  }

  async function remove(threadId: string) {
    try {
      await api.delete(`/chat/threads/${threadId}`)
      await load()
    } catch {
      // silently fail
    }
  }

  watch(pipelineId, load, { immediate: true })

  return { threads, loading, load, create, remove }
}
