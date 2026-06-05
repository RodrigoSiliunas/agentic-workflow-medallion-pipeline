/**
 * usePipelineEditorSession — o "cérebro" do Pipeline Editor V2.
 * Mantém a state machine, mensagens, draft, preview e validação,
 * delegando I/O a usePipelinesApi e usePipelinesStore.
 */
import type {
  StateMachineState,
  SourceOfTruth,
  InspectorTab,
  EditorChatMessage,
  PreviewResultV2,
  ValidationResult,
  FileDiff,
  EditProposal,
  TransformDraft,
  PipelineWorkspace,
  SchemaDelta,
  SchemaColumn,
  ValidationCheck,
} from "~/types/pipeline-editor-v2"

function mapPreview(raw: Record<string, unknown>): PreviewResultV2 {
  return {
    status: (raw.status as "ready" | "running" | "failed") || "ready",
    schemaBefore: raw.schema_before as SchemaColumn[] | undefined,
    schemaAfter: raw.schema_after as SchemaColumn[] | undefined,
    schemaDelta: raw.schema_delta as SchemaDelta | undefined,
    rowsAfter: raw.rows_after as Record<string, unknown>[] | undefined,
    rowsBefore: raw.rows_before as Record<string, unknown>[] | undefined,
    error: raw.error as string | undefined,
  }
}

function mapValidation(raw: Record<string, unknown>): ValidationResult {
  return {
    valid: Boolean(raw.valid),
    checks: (raw.checks as ValidationCheck[] | undefined) || [],
    error: raw.error as string | undefined,
  }
}

export function usePipelineEditorSession(workspace: MaybeRef<PipelineWorkspace | null>) {
  const api = usePipelinesApi()
  const store = usePipelinesStore()

  // ── Chat / flow ─────────────────────────────────────────────────────────
  const messages = ref<EditorChatMessage[]>([])
  const composer = ref("")
  const isStreaming = ref(false)

  // ── Draft / proposal / preview ──────────────────────────────────────────
  const draft = ref<TransformDraft | null>(null)
  const currentProposal = ref<EditProposal | null>(null)
  const preview = ref<PreviewResultV2 | null>(null)
  const previewRunning = ref(false)
  const validation = ref<ValidationResult | null>(null)
  const autoSavedAt = ref<string | null>(null)
  const fileDiffs = ref<FileDiff[]>([])

  // ── State machine ────────────────────────────────────────────────────────
  const stateMachine = ref<StateMachineState>("idle")
  const error = ref<{ title?: string; code?: number; message: string } | null>(null)

  // ── UI ───────────────────────────────────────────────────────────────────
  const sessionsCollapsed = ref(false)
  const inspectorTab = ref<InspectorTab>("rascunho")
  const sourceOfTruth = ref<SourceOfTruth>(null)
  const chatEdits = ref(false)
  const builderEdits = ref(false)

  // Modal flags
  const showApproveModal = ref(false)
  const showShareModal = ref(false)
  const showRevertModal = ref(false)
  const showShortcuts = ref(false)
  const shareUrl = ref<string | null>(null)

  // Model picker
  const selectedProvider = ref("anthropic")
  const selectedModel = ref("claude-sonnet-4.6")

  // ── Derived ──────────────────────────────────────────────────────────────
  const activeSession = computed(
    () => store.editSessions.find((s) => s.id === store.activeEditSessionId) || store.editSessions[0] || null,
  )

  const mode = computed<"chat" | "builder" | "hibrido">(() =>
    chatEdits.value && builderEdits.value
      ? "hibrido"
      : sourceOfTruth.value === "builder"
        ? "builder"
        : "chat",
  )

  const canApprove = computed(
    () =>
      preview.value?.status === "ready" &&
      validation.value?.valid === true &&
      stateMachine.value !== "pr_created",
  )

  const approveBlockReason = computed<string | null>(() => {
    if (!preview.value) return "Rode o preview primeiro"
    if (preview.value.status !== "ready") return "Preview não está pronto"
    if (!validation.value?.valid) return "Validação falhou — corrija os erros antes de aprovar"
    if (stateMachine.value === "pr_created") return "PR já aberto"
    return null
  })

  // ── Helpers ──────────────────────────────────────────────────────────────
  function now() {
    return new Date().toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit" })
  }

  function pipelineId() {
    return toValue(workspace)?.id || ""
  }

  // Garante uma sessão de edição ativa, sem depender de store.workspace
  async function ensureSession(title = "Edição via NL") {
    const ws = toValue(workspace)
    if (!ws) throw new Error("Workspace não carregado")
    const existing = activeSession.value
    if (existing) return existing
    const session = await api.createEditSession(ws.id, title)
    store.editSessions = [session, ...store.editSessions]
    store.activeEditSessionId = session.id
    return session
  }

  function reset() {
    messages.value = []
    draft.value = null
    currentProposal.value = null
    preview.value = null
    validation.value = null
    fileDiffs.value = []
    stateMachine.value = "idle"
    error.value = null
    chatEdits.value = false
    builderEdits.value = false
    sourceOfTruth.value = null
    autoSavedAt.value = null
    isStreaming.value = false
    previewRunning.value = false
  }

  // ── Actions ──────────────────────────────────────────────────────────────
  async function sendNL(content: string) {
    if (!content?.trim()) return
    chatEdits.value = true
    sourceOfTruth.value = "chat"
    const t = now()
    messages.value = [...messages.value, { role: "user", author: "Você", time: t, content }]
    composer.value = ""
    isStreaming.value = true
    stateMachine.value = "generating_proposal"
    messages.value = [...messages.value, { role: "assistant", time: t, content: "", streaming: true }]

    try {
      const session = await ensureSession("Edição via NL")
      if (!session) throw new Error("Não foi possível criar sessão de edição")
      const response = await api.sendEditMessage(pipelineId(), session.id, content, draft.value || undefined)

      isStreaming.value = false
      stateMachine.value = "idle"
      messages.value = [
        ...messages.value.slice(0, -1),
        { role: "assistant", time: t, content: response.message, proposal: response.proposal },
      ]
      currentProposal.value = response.proposal
      draft.value = response.proposal.draft
      inspectorTab.value = "rascunho"
    } catch (e) {
      isStreaming.value = false
      stateMachine.value = "error"
      error.value = {
        title: "Falha ao gerar proposta",
        message: e instanceof Error ? e.message : "Erro desconhecido ao comunicar com o agente",
        code: 500,
      }
    }
  }

  function applyProposalToDraft() {
    if (!currentProposal.value) return
    // Não marca builder como active — a origem é o chat (RF-C)
    draft.value = currentProposal.value.draft
    inspectorTab.value = "rascunho"
  }

  function markBuilderActive() {
    builderEdits.value = true
    sourceOfTruth.value = "builder"
    autoSavedAt.value = "agora"
  }

  // NF-07: autosave debounced manual (1s); só quando sourceOfTruth === "builder"
  let _autosaveTimer: ReturnType<typeof setTimeout> | null = null

  function cancelAutosave() {
    if (_autosaveTimer) { clearTimeout(_autosaveTimer); _autosaveTimer = null }
  }

  function scheduleAutosave(d: TransformDraft) {
    cancelAutosave()
    _autosaveTimer = setTimeout(async () => {
      _autosaveTimer = null
      const ws = toValue(workspace)
      if (!ws) return
      const session = activeSession.value
      if (!session) return
      try {
        await api.updateDraft(ws.id, session.id, d)
        autoSavedAt.value = now()
      } catch { /* silently ignore autosave failures */ }
    }, 1000)
  }

  onUnmounted(cancelAutosave)

  watch(
    draft,
    (d) => {
      if (d && sourceOfTruth.value === "builder") {
        scheduleAutosave(d)
      }
    },
    { deep: true },
  )

  async function saveDraft(d?: TransformDraft | null) {
    const target = d ?? draft.value
    if (!target) return
    const ws = toValue(workspace)
    if (!ws) return
    const session = await ensureSession("Rascunho")
    cancelAutosave()
    try {
      await api.updateDraft(ws.id, session.id, target)
      autoSavedAt.value = now()
    } catch (e) {
      error.value = {
        title: "Erro ao salvar rascunho",
        message: e instanceof Error ? e.message : "Falha ao salvar",
      }
    }
  }

  async function runPreview() {
    const ws = toValue(workspace)
    if (!ws) return
    const session = await ensureSession("Preview")
    // Aguarda autosave pendente antes de rodar preview
    cancelAutosave()
    if (draft.value && sourceOfTruth.value === "builder") {
      try { await api.updateDraft(ws.id, session.id, draft.value) } catch { /* ignore */ }
    }
    stateMachine.value = "running_preview"
    previewRunning.value = true
    error.value = null
    inspectorTab.value = "preview"
    try {
      const raw = await api.getPreview(ws.id, session.id, 50)
      preview.value = mapPreview(raw)
      stateMachine.value = "idle"
      previewRunning.value = false
    } catch (e) {
      previewRunning.value = false
      stateMachine.value = "error"
      error.value = {
        title: "Falha no preview",
        message: e instanceof Error ? e.message : "Erro ao rodar preview Databricks",
      }
    }
  }

  async function confirmApprove() {
    const ws = toValue(workspace)
    if (!ws) return
    const session = await ensureSession("Aprovar")
    showApproveModal.value = false
    stateMachine.value = "validating"
    // Mostra validação em progresso
    validation.value = {
      valid: false,
      checks: [
        { label: "Codegen PySpark", state: "running" },
        { label: "Ruff lint", state: "pending" },
        { label: "Schema compatível", state: "pending" },
        { label: "Marker injetado", state: "pending" },
      ],
    }
    try {
      const result = await api.approveEdit(ws.id, session.id)
      if (result.validation) validation.value = mapValidation(result.validation as Record<string, unknown>)
      if (result.diff) fileDiffs.value = result.diff
      stateMachine.value = "opening_pr"
      // Simula transição para pr_created (streaming não disponível no backend)
      await new Promise((r) => setTimeout(r, 600))
      stateMachine.value = "pr_created"
      // Atualiza sessão na store
      const idx = store.editSessions.findIndex((s) => s.id === session.id)
      if (idx !== -1) {
        store.editSessions[idx] = { ...store.editSessions[idx], status: "pr_created" }
      }
      inspectorTab.value = "pr"
    } catch (e) {
      stateMachine.value = "error"
      error.value = {
        title: "Falha ao aprovar e abrir PR",
        message: e instanceof Error ? e.message : "Erro ao criar PR no GitHub",
      }
    }
  }

  async function confirmRevert(revertMode: "draft" | "revert_pr" | "close_pr") {
    const ws = toValue(workspace)
    if (!ws) return
    const session = activeSession.value
    if (!session) return
    showRevertModal.value = false
    try {
      await api.revertEdit(ws.id, session.id, revertMode)
      stateMachine.value = "idle"
      const idx = store.editSessions.findIndex((s) => s.id === session.id)
      if (idx !== -1) {
        store.editSessions[idx] = { ...store.editSessions[idx], status: "draft" }
      }
      const t = now()
      messages.value = [
        ...messages.value,
        {
          role: "assistant",
          time: t,
          content: `PR revertido via mode="${revertMode}". Sessão voltou para rascunho.`,
        },
      ]
    } catch (e) {
      error.value = {
        title: "Falha ao reverter",
        message: e instanceof Error ? e.message : "Erro ao reverter PR",
      }
    }
  }

  async function share() {
    const ws = toValue(workspace)
    if (!ws) return
    const session = activeSession.value
    if (!session) return
    try {
      const result = await api.shareArtifact(ws.id, session.id) as Record<string, unknown>
      shareUrl.value = String(result.url || result.token || "")
      showShareModal.value = true
    } catch (e) {
      error.value = {
        title: "Falha ao compartilhar",
        message: e instanceof Error ? e.message : "Erro ao gerar link de compartilhamento",
      }
    }
  }

  async function newSession() {
    const ws = toValue(workspace)
    if (!ws) return
    const session = await api.createEditSession(ws.id, "Nova edição")
    store.editSessions = [session, ...store.editSessions]
    store.activeEditSessionId = session.id
    reset()
  }

  function dismissError() {
    error.value = null
    if (stateMachine.value === "error") stateMachine.value = "idle"
  }

  function retry() {
    error.value = null
    stateMachine.value = "idle"
  }

  return {
    // State
    messages,
    composer,
    isStreaming,
    draft,
    currentProposal,
    preview,
    previewRunning,
    validation,
    autoSavedAt,
    fileDiffs,
    stateMachine,
    error,
    sessionsCollapsed,
    inspectorTab,
    sourceOfTruth,
    chatEdits,
    builderEdits,
    showApproveModal,
    showShareModal,
    showRevertModal,
    showShortcuts,
    shareUrl,
    selectedProvider,
    selectedModel,
    // Derived
    activeSession,
    mode,
    canApprove,
    approveBlockReason,
    // Actions
    sendNL,
    saveDraft,
    applyProposalToDraft,
    markBuilderActive,
    runPreview,
    confirmApprove,
    confirmRevert,
    share,
    newSession,
    dismissError,
    retry,
  }
}
