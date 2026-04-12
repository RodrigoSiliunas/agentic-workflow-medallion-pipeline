/**
 * Pipelines store — wirado em usePipelinesApi.
 * Mock branching foi movido para usePipelinesApi (Strategy pattern).
 */
import { defineStore } from "pinia"
import type { Pipeline } from "~/types/pipeline"

export const usePipelinesStore = defineStore("pipelines", () => {
  const pipelines = ref<Pipeline[]>([])
  const activePipelineId = ref<string>("")
  const loaded = ref(false)

  async function load(force = false) {
    if (loaded.value && !force) return
    try {
      const api = usePipelinesApi()
      pipelines.value = await api.list()
      if (!activePipelineId.value && pipelines.value[0]) {
        activePipelineId.value = pipelines.value[0].id
      }
      loaded.value = true
    } catch (e) {
      console.error("Failed to load pipelines", e)
      pipelines.value = []
      loaded.value = true
    }
  }

  const activePipeline = computed(
    () => pipelines.value.find((p) => p.id === activePipelineId.value) || null,
  )

  function getById(id: string): Pipeline | undefined {
    return pipelines.value.find((p) => p.id === id)
  }

  function setActive(id: string) {
    if (pipelines.value.some((p) => p.id === id)) {
      activePipelineId.value = id
    }
  }

  return {
    pipelines,
    activePipelineId,
    activePipeline,
    loaded,
    load,
    getById,
    setActive,
  }
})
