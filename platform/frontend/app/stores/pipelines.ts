/**
 * Pipelines store — wirado em usePipelinesApi.
 * Mock branching foi movido para usePipelinesApi (Strategy pattern).
 */
import { defineStore } from "pinia"
import type { Pipeline } from "~/types/pipeline"
import type {
  PipelineEditSession,
  PipelineWorkspace,
  TransformDraft,
} from "~/types/pipeline-editor"

export const usePipelinesStore = defineStore("pipelines", () => {
  const pipelines = ref<Pipeline[]>([])
  const activePipelineId = ref<string>("")
  const workspace = ref<PipelineWorkspace | null>(null)
  const editSessions = ref<PipelineEditSession[]>([])
  const activeEditSessionId = ref<string>("")
  const activeDraft = ref<TransformDraft | null>(null)
  const preview = ref<Record<string, unknown> | null>(null)
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

  async function loadWorkspace(id: string) {
    const api = usePipelinesApi()
    workspace.value = await api.getWorkspace(id)
    activePipelineId.value = id
    editSessions.value = await api.listEditSessions(id)
    if (!activeEditSessionId.value && editSessions.value[0]) {
      activeEditSessionId.value = editSessions.value[0].id
    }
  }

  async function ensureEditSession(title?: string) {
    if (!workspace.value) throw new Error("Workspace de pipeline nao carregado")
    if (activeEditSessionId.value) {
      return editSessions.value.find((s) => s.id === activeEditSessionId.value) || null
    }
    const api = usePipelinesApi()
    const session = await api.createEditSession(workspace.value.id, title)
    editSessions.value = [session, ...editSessions.value]
    activeEditSessionId.value = session.id
    return session
  }

  async function saveDraft(draft: TransformDraft) {
    if (!workspace.value) throw new Error("Workspace de pipeline nao carregado")
    const session = await ensureEditSession("Low-code draft")
    if (!session) throw new Error("Sessao de edicao nao encontrada")
    const api = usePipelinesApi()
    const version = await api.updateDraft(workspace.value.id, session.id, draft)
    activeDraft.value = version.draft
    preview.value = null
    return version
  }

  async function runPreview(sampleRows = 50) {
    if (!workspace.value || !activeEditSessionId.value) {
      throw new Error("Sessao de edicao nao encontrada")
    }
    const api = usePipelinesApi()
    preview.value = await api.getPreview(workspace.value.id, activeEditSessionId.value, sampleRows)
    return preview.value
  }

  return {
    pipelines,
    activePipelineId,
    activePipeline,
    workspace,
    editSessions,
    activeEditSessionId,
    activeDraft,
    preview,
    loaded,
    load,
    getById,
    setActive,
    loadWorkspace,
    ensureEditSession,
    saveDraft,
    runPreview,
  }
})
