<script setup lang="ts">
import type { PipelineWorkspace, PipelineEditSession, SessionStatusV2 } from "~/types/pipeline-editor-v2"

const props = defineProps<{
  workspace: PipelineWorkspace
  sessions?: PipelineEditSession[]
}>()

// ── Composables ────────────────────────────────────────────────────────────
const workspaceRef = computed(() => props.workspace)
const session = usePipelineEditorSession(workspaceRef)
const { settings } = useEditorSettings()

// ── STT mock ───────────────────────────────────────────────────────────────
const dictation = useMockDictation((text) => {
  session.composer.value = text
})

// ── Atalhos de teclado (NF-03) ─────────────────────────────────────────────
useEditorShortcuts({
  onSend: () => session.sendNL(session.composer.value),
  onSaveDraft: () => session.saveDraft(),
  onRunPreview: () => session.runPreview(),
  onNewSession: () => session.newSession(),
  onShare: () => session.share(),
  onHelp: () => { session.showShortcuts.value = true },
  onEscape: () => {
    if (session.showApproveModal.value) { session.showApproveModal.value = false; return }
    if (session.showShareModal.value) { session.showShareModal.value = false; return }
    if (session.showRevertModal.value) { session.showRevertModal.value = false; return }
    if (session.showShortcuts.value) { session.showShortcuts.value = false; return }
  },
})

// ── Computed helpers ───────────────────────────────────────────────────────
const activeSession = computed(() => session.activeSession.value)

// Status do header derivado da jornada atual (state machine), não do status
// persistido da sessão — assim a pill fica coerente com o stepper (Rascunho=âmbar).
const headerStatus = computed<SessionStatusV2>(() => {
  switch (session.stateMachine.value) {
    case "pr_created":
      return "pr_created"
    case "validation_failed":
    case "error":
      return "validation_failed"
    default:
      return "draft"
  }
})

// Sessão exibida no header com status sobreposto pela jornada
const headerSession = computed(() => ({
  id: activeSession.value?.id ?? "",
  status: headerStatus.value,
}))

// Nome exibido no header — usa o slug do template (ex: pipeline-seguradora-whatsapp),
// com fallback para o nome amigável do workspace.
const pipelineName = computed(
  () => props.workspace.manifest?.templateSlug || props.workspace.name,
)
const layer = computed(() => {
  const node = props.workspace.manifest.nodes[0]
  if (!node) return "Silver"
  return node.layer.charAt(0).toUpperCase() + node.layer.slice(1)
})
const targetNode = computed(() => session.targetNodeKey.value || props.workspace.manifest.nodes[0]?.taskKey || "")
const targetTable = computed(() => session.targetTable.value || props.workspace.manifest.nodes[0]?.outputTables[0] || "")

// ── Local wizard/tabbed state ──────────────────────────────────────────────
const wizardStep = ref(0)
const tabbedTab = ref("Chat")

// ── Handlers ──────────────────────────────────────────────────────────────
function handleSend() {
  session.sendNL(session.composer.value)
}

function handleSuggestion(text: string) {
  session.composer.value = text
  session.sendNL(text)
}

function handleApprove() {
  session.confirmApprove()
}

function handleRevert(mode: string) {
  session.confirmRevert(mode as "draft" | "revert_pr" | "close_pr")
}

function handleSelectSession(id: string) {
  const store = usePipelinesStore()
  store.setActiveEditSession(id)
}

// ── Jump-to demo (apenas em dev) ──────────────────────────────────────────
const MOCK_INITIAL_MESSAGES = import.meta.dev
  ? [
      { role: "user" as const, author: "Rodrigo", time: "14:18", content: "Renomeie cliente_id para customer_id em silver.messages e remova a coluna ssn" },
      { role: "assistant" as const, time: "14:18", content: "Vou montar a proposta — três operações na camada Silver." },
    ]
  : []

function jumpTo(state: string) {
  if (!import.meta.dev) return
  if (state === "zero") {
    session.messages.value = []
    session.draft.value = null
    session.stateMachine.value = "idle"
    return
  }
  if (state === "j1_with_proposal") {
    session.messages.value = [...MOCK_INITIAL_MESSAGES]
    session.stateMachine.value = "idle"
  }
  if (state === "j2_preview_ok") {
    session.messages.value = [...MOCK_INITIAL_MESSAGES]
    session.inspectorTab.value = "preview"
  }
  if (state === "error") {
    session.error.value = { title: "Falha ao gerar proposta", message: "Timeout na validação E2E", code: 500 }
    session.stateMachine.value = "error"
  }
}
</script>

<template>
  <!-- Organism raiz do Pipeline Editor V2 — conectado a usePipelineEditorSession -->
  <div class="editor-root" :data-density="settings.density">

    <!-- =================================================================
         Layout: tri_pane (padrão), chat_dominant, conservative
         ================================================================= -->
    <template v-if="['tri_pane', 'chat_dominant', 'conservative'].includes(settings.layout)">
      <div class="tri-pane-layout">
        <!-- Cabeçalho do workspace -->
        <EditorWorkspaceHeader
          :pipeline-name="pipelineName"
          :layer="layer"
          :target-node="targetNode"
          :target-table="targetTable"
          :mode="session.mode.value"
          :session="headerSession"
          @new-session="session.newSession()"
          @share="session.share()"
          @history="() => {}"
          @help="session.showShortcuts.value = true"
        >
          <template #actions>
            <EditorSettingsPopover :settings="settings" @update:settings="(s) => Object.assign(settings, s)" @jump-to="jumpTo" />
          </template>
        </EditorWorkspaceHeader>

        <!-- Timeline de estado (opcional) -->
        <EditorStateTimeline
          v-if="settings.showStateTimeline"
          :current="session.stateMachine.value"
          :error="session.error.value?.message"
          @retry="session.retry()"
        />

        <!-- Banner de erro global -->
        <EditorErrorBanner
          v-if="session.error.value"
          :error="session.error.value"
          @dismiss="session.dismissError()"
          @retry="session.retry()"
        />

        <!-- Banner NF-01: aviso em telas pequenas (<1024px) -->
        <div
          v-if="useMediaQuery('(max-width:1023px)').value"
          role="alert"
          class="px-4 py-2 text-xs text-center"
          style="background: var(--status-warning-bg, #fef3c7); color: var(--status-warning, #92400e)"
        >
          O Pipeline Editor foi projetado para telas maiores. Para melhor experiência, use uma tela ≥ 1024px.
        </div>

        <!-- Corpo principal: rail + chat + inspector -->
        <div class="tri-body">
          <!-- Rail de sessões (opcional) -->
          <EditorSessionsRail
            v-if="settings.showSessionsRail"
            :sessions="sessions || []"
            :active-id="activeSession?.id || ''"
            :collapsed="session.sessionsCollapsed.value"
            @select="handleSelectSession"
            @new="session.newSession()"
            @toggle="session.sessionsCollapsed.value = !session.sessionsCollapsed.value"
          />

          <!-- Painel de chat -->
          <div
            class="chat-pane"
            :class="{
              'chat-dominant': settings.layout === 'chat_dominant',
            }"
          >
            <EditorChatPane
              :messages="session.messages.value"
              :is-streaming="session.isStreaming.value"
              :source-of-truth="session.sourceOfTruth.value"
              :show-zero-state="session.messages.value.length === 0"
              @preview-proposal="session.runPreview()"
              @adjust-in-builder="() => { session.inspectorTab.value = 'rascunho'; session.markBuilderActive() }"
              @apply-proposal="session.applyProposalToDraft()"
              @suggestion="handleSuggestion"
            />
            <EditorComposer
              :model-value="session.composer.value"
              :disabled="session.isStreaming.value"
              :is-listening="dictation.listening.value"
              @update:model-value="session.composer.value = $event"
              @send="handleSend"
              @toggle-listen="dictation.toggle()"
            />
          </div>

          <!-- Painel do inspector -->
          <div
            class="inspector-pane"
            :class="{
              'inspector-narrow': settings.layout === 'chat_dominant',
              'inspector-conservative': settings.layout === 'conservative',
            }"
          >
            <EditorInspectorPane
              :inspector-tab="session.inspectorTab.value"
              :source-of-truth="session.sourceOfTruth.value"
              :draft="session.draft.value"
              :preview="session.preview.value"
              :running="session.previewRunning.value"
              :validation="session.validation.value"
              :session="activeSession"
              :proposal="session.currentProposal.value"
              :operations="session.draft.value?.operations || []"
              :file-diffs="session.fileDiffs.value"
              :table-columns="session.tableColumns.value"
              :nodes="session.manifestNodes.value"
              :selected-node-id="session.selectedNodeId.value"
              @select-node="session.selectTargetNode($event)"
              @update:inspector-tab="session.inspectorTab.value = $event"
              @update:draft="session.draft.value = $event"
              @mark-builder-active="session.markBuilderActive()"
              @run-preview="session.runPreview()"
              @export="(fmt) => {}"
              @approve="session.showApproveModal.value = true"
              @share="session.share()"
              @revert="session.showRevertModal.value = true"
            />
          </div>
        </div>
      </div>
    </template>

    <!-- =================================================================
         Layout: wizard
         ================================================================= -->
    <template v-else-if="settings.layout === 'wizard'">
      <EditorWizardLayout
        :steps="['Chat', 'Builder', 'Preview', 'PR']"
        :current-step="wizardStep"
        @update:current-step="wizardStep = $event"
      >
        <div v-if="wizardStep === 0" class="wizard-step-content">
          <EditorChatPane
            :messages="session.messages.value"
            :is-streaming="session.isStreaming.value"
            :source-of-truth="session.sourceOfTruth.value"
            :show-zero-state="session.messages.value.length === 0"
            @preview-proposal="session.runPreview()"
            @adjust-in-builder="() => { session.inspectorTab.value = 'rascunho'; session.markBuilderActive() }"
            @apply-proposal="session.applyProposalToDraft()"
            @suggestion="handleSuggestion"
          />
          <EditorComposer
            :model-value="session.composer.value"
            :disabled="session.isStreaming.value"
            :is-listening="dictation.listening.value"
            @update:model-value="session.composer.value = $event"
            @send="handleSend"
            @toggle-listen="dictation.toggle()"
          />
        </div>
        <div v-else-if="wizardStep === 1" class="wizard-step-content">
          <EditorTransformBuilder
            :draft="session.draft.value"
            :source-of-truth="session.sourceOfTruth.value"
            :table-columns="session.tableColumns.value"
            :nodes="session.manifestNodes.value"
            :selected-node-id="session.selectedNodeId.value"
            @select-node="session.selectTargetNode($event)"
            @update:draft="session.draft.value = $event"
            @mark-builder-active="session.markBuilderActive()"
          />
        </div>
        <div v-else-if="wizardStep === 2" class="wizard-step-content">
          <EditorPreviewPanel
            :preview="session.preview.value"
            :running="session.previewRunning.value"
            @run-preview="session.runPreview()"
            @export="(fmt) => {}"
          />
        </div>
        <div v-else-if="wizardStep === 3" class="wizard-step-content">
          <EditorPrPanel
            v-if="activeSession"
            :proposal="session.currentProposal.value"
            :preview="session.preview.value"
            :validation="session.validation.value"
            :session="activeSession"
            :file-diffs="session.fileDiffs.value"
            @approve="session.showApproveModal.value = true"
            @share="session.share()"
            @revert="session.showRevertModal.value = true"
          />
        </div>
      </EditorWizardLayout>
    </template>

    <!-- =================================================================
         Layout: tabbed
         ================================================================= -->
    <template v-else-if="settings.layout === 'tabbed'">
      <EditorTabbedLayout
        :tabs="['Chat', 'Builder', 'Preview', 'PR']"
        :model-value="tabbedTab"
        @update:model-value="tabbedTab = $event"
      >
        <div v-if="tabbedTab === 'Chat'" class="tabbed-step-content">
          <EditorChatPane
            :messages="session.messages.value"
            :is-streaming="session.isStreaming.value"
            :source-of-truth="session.sourceOfTruth.value"
            :show-zero-state="session.messages.value.length === 0"
            @preview-proposal="session.runPreview()"
            @adjust-in-builder="() => { session.inspectorTab.value = 'rascunho'; session.markBuilderActive() }"
            @apply-proposal="session.applyProposalToDraft()"
            @suggestion="handleSuggestion"
          />
          <EditorComposer
            :model-value="session.composer.value"
            :disabled="session.isStreaming.value"
            :is-listening="dictation.listening.value"
            @update:model-value="session.composer.value = $event"
            @send="handleSend"
            @toggle-listen="dictation.toggle()"
          />
        </div>
        <div v-else-if="tabbedTab === 'Builder'" class="tabbed-step-content">
          <EditorTransformBuilder
            :draft="session.draft.value"
            :source-of-truth="session.sourceOfTruth.value"
            :table-columns="session.tableColumns.value"
            :nodes="session.manifestNodes.value"
            :selected-node-id="session.selectedNodeId.value"
            @select-node="session.selectTargetNode($event)"
            @update:draft="session.draft.value = $event"
            @mark-builder-active="session.markBuilderActive()"
          />
        </div>
        <div v-else-if="tabbedTab === 'Preview'" class="tabbed-step-content">
          <EditorPreviewPanel
            :preview="session.preview.value"
            :running="session.previewRunning.value"
            @run-preview="session.runPreview()"
            @export="(fmt) => {}"
          />
        </div>
        <div v-else-if="tabbedTab === 'PR'" class="tabbed-step-content">
          <EditorPrPanel
            v-if="activeSession"
            :proposal="session.currentProposal.value"
            :preview="session.preview.value"
            :validation="session.validation.value"
            :session="activeSession"
            :file-diffs="session.fileDiffs.value"
            @approve="session.showApproveModal.value = true"
            @share="session.share()"
            @revert="session.showRevertModal.value = true"
          />
        </div>
      </EditorTabbedLayout>
    </template>

    <!-- =================================================================
         Modais
         ================================================================= -->
    <EditorApproveModal
      :open="session.showApproveModal.value"
      :session="activeSession"
      :proposal="session.currentProposal.value"
      :preview="session.preview.value"
      @close="session.showApproveModal.value = false"
      @confirm="handleApprove"
    />

    <EditorShareModal
      :open="session.showShareModal.value"
      :session="activeSession"
      @close="session.showShareModal.value = false"
    />

    <EditorRevertModal
      :open="session.showRevertModal.value"
      :session="activeSession"
      @close="session.showRevertModal.value = false"
      @confirm="handleRevert"
    />

    <EditorShortcutSheet
      :open="session.showShortcuts.value"
      @close="session.showShortcuts.value = false"
    />
  </div>
</template>

<style scoped>
.editor-root {
  display: flex;
  flex-direction: column;
  height: 100%;
  overflow: hidden;
  background: var(--bg);
  font-family: var(--font-sans);
}

.tri-pane-layout {
  display: flex;
  flex-direction: column;
  height: 100%;
  overflow: hidden;
}

.tri-body {
  display: flex;
  flex-direction: row;
  flex: 1;
  min-height: 0;
  overflow: hidden;
}

.chat-pane {
  /* Proto tri_pane (default): chat flex 1.15 vs inspector flex 1 */
  flex: 1.15;
  min-width: 0;
  display: flex;
  flex-direction: column;
  border-right: 1px solid var(--border);
}

.chat-dominant {
  /* Proto chat_dominant: chat flex 1.6 vs inspector flex 1 */
  flex: 1.6;
}

.inspector-pane {
  /* Proto: inspector é flex 1 (não largura fixa) */
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.inspector-conservative {
  width: 320px;
  flex: 0 0 auto;
}

.inspector-narrow {
  width: 320px;
  flex: 0 0 auto;
}

.wizard-step-content {
  display: flex;
  flex-direction: column;
  height: 100%;
  overflow: hidden;
}

.tabbed-step-content {
  display: flex;
  flex-direction: column;
  height: 100%;
  overflow: hidden;
}

.editor-root[data-density="compact"] {
  --editor-spacing: 6px;
  font-size: 12px;
}

.editor-root[data-density="comfortable"] {
  --editor-spacing: 10px;
  font-size: 13px;
}
</style>
