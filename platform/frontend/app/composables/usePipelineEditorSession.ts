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

function mapSchemaDelta(raw: unknown): SchemaDelta | undefined {
  if (!raw || typeof raw !== "object") return undefined
  const delta = raw as Record<string, unknown>
  // Backend serializa `dropped`; o frontend usa `removed`.
  return {
    removed: delta.dropped as string[] | undefined,
    renamed: delta.renamed as SchemaDelta["renamed"],
    derived: delta.derived as SchemaDelta["derived"],
  }
}

function mapPreview(raw: Record<string, unknown>): PreviewResultV2 {
  return {
    status: (raw.status as "ready" | "running" | "failed") || "ready",
    schemaBefore: raw.schema_before as SchemaColumn[] | undefined,
    schemaAfter: raw.schema_after as SchemaColumn[] | undefined,
    schemaDelta: mapSchemaDelta(raw.schema_delta),
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

  // A validação (C2) roda DENTRO do approve no backend e só existe como
  // resultado dele — exigi-la antes do clique criava um deadlock em que o
  // botão nunca habilitava. Gate correto: preview pronto + PR ainda não aberto.
  const canApprove = computed(
    () =>
      preview.value?.status === "ready" &&
      stateMachine.value !== "pr_created",
  )

  const approveBlockReason = computed<string | null>(() => {
    if (!preview.value) return "Rode o preview primeiro"
    if (preview.value.status !== "ready") return "Preview não está pronto"
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

  // Draft mudou → o backend cria uma NOVA versão a cada updateDraft e o
  // approve exige preview fresco dessa versão. Invalida os artefatos da
  // versão anterior pra UI não exibir um preview/validação obsoletos.
  function invalidateRunArtifacts() {
    preview.value = null
    validation.value = null
  }

  // ── Node alvo + colunas REAIS da tabela (builder) ────────────────────────
  // O manifest do workspace traz apenas nodes Silver (editor é Silver-only);
  // o builder seleciona um deles e o ColumnPicker carrega o schema verdadeiro
  // da tabela via GET /pipelines/{id}/columns (information_schema).
  const selectedNodeId = ref<string | null>(null)
  const tableColumns = ref<SchemaColumn[]>([])
  const columnsLoading = ref(false)

  const manifestNodes = computed(() => toValue(workspace)?.manifest.nodes ?? [])
  const targetManifestNode = computed(
    () =>
      manifestNodes.value.find((n) => n.id === selectedNodeId.value) ??
      manifestNodes.value[0] ??
      null,
  )
  const targetNodeKey = computed(() => targetManifestNode.value?.taskKey ?? "")
  const targetTable = computed(() => targetManifestNode.value?.outputTables[0] ?? "")

  async function loadTableColumns() {
    const ws = toValue(workspace)
    const table = targetTable.value
    if (!ws || !table) return
    columnsLoading.value = true
    try {
      tableColumns.value = await api.getTableColumns(ws.id, table)
    } catch {
      // Sem colunas o picker continua usável (digitação manual / allowCreate)
      tableColumns.value = []
    } finally {
      columnsLoading.value = false
    }
  }

  watch(targetTable, () => { loadTableColumns() }, { immediate: true })

  function selectTargetNode(nodeId: string) {
    selectedNodeId.value = nodeId
    // Mantém o draft coerente com o node recém-selecionado
    if (draft.value) {
      draft.value = {
        ...draft.value,
        targetNode: targetNodeKey.value,
        targetTable: targetTable.value,
      }
    }
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
      invalidateRunArtifacts()
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
    invalidateRunArtifacts()
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
        invalidateRunArtifacts()
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
      invalidateRunArtifacts()
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

      // O backend devolve 200 com status de gate de segurança quando o approve
      // é barrado: C3 (downstream_blocked) e C2 (validation_failed). Não são
      // sucesso — exibir o motivo e NÃO transicionar para pr_created.
      if (result.status === "downstream_blocked") {
        const impact = result.downstream_impact as
          | { affected?: { column: string; references?: { file: string }[] }[] }
          | undefined
        const affected = impact?.affected || []
        const cols = affected.map((a) => a.column).join(", ")
        const files = [...new Set(affected.flatMap((a) => (a.references || []).map((r) => r.file)))]
        validation.value = {
          valid: false,
          checks: [{ label: "Impacto downstream", state: "fail" }],
          error: `Coluna(s) ${cols} referenciada(s) downstream em ${files.length} notebook(s).`,
        }
        stateMachine.value = "validation_failed"
        error.value = {
          title: "Aprovação bloqueada por impacto downstream",
          message:
            `A(s) coluna(s) ${cols} é(são) usada(s) por: ` +
            `${files.slice(0, 5).join(", ")}${files.length > 5 ? "…" : ""}. ` +
            "Ajuste o draft para colunas sem referências downstream.",
        }
        inspectorTab.value = "pr"
        return
      }
      if (result.status === "validation_failed") {
        stateMachine.value = "validation_failed"
        error.value = {
          title: "Validação pré-PR rejeitou o código gerado",
          message: validation.value?.error || "Corrija o draft e tente novamente.",
        }
        inspectorTab.value = "pr"
        return
      }

      // PR retornado pelo backend (number/url ja normalizados em usePipelinesApi)
      const pr = result.pr as { number?: number; url?: string } | undefined
      stateMachine.value = "opening_pr"
      // Simula transição para pr_created (streaming não disponível no backend)
      await new Promise((r) => setTimeout(r, 600))
      stateMachine.value = "pr_created"
      // Atualiza sessão na store, persistindo o PR aberto
      const idx = store.editSessions.findIndex((s) => s.id === session.id)
      if (idx !== -1) {
        store.editSessions[idx] = {
          ...store.editSessions[idx],
          status: "pr_created",
          prNumber: pr?.number ?? null,
          prUrl: pr?.url ?? null,
        }
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
    // Node alvo + colunas reais (builder)
    selectedNodeId,
    manifestNodes,
    targetManifestNode,
    targetNodeKey,
    targetTable,
    tableColumns,
    columnsLoading,
    loadTableColumns,
    selectTargetNode,
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
