<script setup lang="ts">
import type {
  StateMachineState,
  SourceOfTruth,
  InspectorTab,
  EditorChatMessage,
  PreviewResultV2,
  ValidationResult,
  FileDiff,
  EditorSettings,
  TransformDraft,
  EditProposal,
  PipelineEditSession,
} from "~/types/pipeline-editor-v2"

// ---------------------------------------------------------------------------
// Props
// ---------------------------------------------------------------------------
const props = withDefaults(defineProps<{
  pipelineName?: string
  layer?: string
  targetNode?: string
  targetTable?: string
  sessions?: PipelineEditSession[]
  activeSessionId?: string
  messages?: EditorChatMessage[]
  isStreaming?: boolean
  draft?: TransformDraft | null
  proposal?: EditProposal | null
  preview?: PreviewResultV2 | null
  previewRunning?: boolean
  validation?: ValidationResult | null
  autoSavedAt?: string | null
  stateMachine?: StateMachineState
  error?: { title?: string; code?: number; message: string } | null
  sourceOfTruth?: SourceOfTruth
  inspectorTab?: InspectorTab
  settings?: EditorSettings
  fileDiffs?: FileDiff[]
}>(), {
  pipelineName: "pipeline-seguradora-whatsapp",
  layer: "Silver",
  targetNode: "silver_messages",
  targetTable: "silver.messages",
  sessions: () => [],
  activeSessionId: "",
  messages: () => [],
  isStreaming: false,
  draft: null,
  proposal: null,
  preview: null,
  previewRunning: false,
  validation: null,
  autoSavedAt: null,
  stateMachine: "idle",
  error: null,
  sourceOfTruth: null,
  inspectorTab: "rascunho",
  settings: () => ({
    layout: "tri_pane",
    density: "comfortable",
    showSessionsRail: true,
    showStateTimeline: true,
  }),
  fileDiffs: () => [],
})

// ---------------------------------------------------------------------------
// Emits
// ---------------------------------------------------------------------------
const emit = defineEmits<{
  newSession: []
  share: []
  history: []
  help: []
  retry: []
  dismissError: []
  sendMessage: [content: string]
  toggleListen: []
  previewProposal: []
  adjustInBuilder: []
  applyProposal: []
  runPreview: []
  export: [format: string]
  approve: []
  revert: []
  suggest: [text: string]
  "update:inspectorTab": [tab: InspectorTab]
  "update:draft": [draft: TransformDraft]
  markBuilderActive: []
  "update:settings": [settings: EditorSettings]
  "update:activeSessionId": [id: string]
  showApproveModal: [open: boolean]
  showShareModal: [open: boolean]
  showRevertModal: [open: boolean]
  showShortcuts: [open: boolean]
}>()

// ---------------------------------------------------------------------------
// Estado local
// ---------------------------------------------------------------------------
const composer = ref("")
const listening = ref(false)
const approveOpen = ref(false)
const shareOpen = ref(false)
const revertOpen = ref(false)
const shortcutsOpen = ref(false)
const historyOpen = ref(false)
const sessionsCollapsed = ref(false)

// Controle do wizard
const wizardStep = ref(0)
// Aba ativa no tabbed layout
const tabbedTab = ref(props.sessions[0]?.id || "Chat")

// ---------------------------------------------------------------------------
// Computed
// ---------------------------------------------------------------------------
const activeSession = computed(
  () =>
    props.sessions.find((s) => s.id === props.activeSessionId) ||
    props.sessions[0] ||
    null
)

const mode = computed(() =>
  props.sourceOfTruth === "builder" ? "builder" : "chat"
)

// ---------------------------------------------------------------------------
// Handlers
// ---------------------------------------------------------------------------
function handleSend() {
  if (!composer.value.trim()) return
  emit("sendMessage", composer.value)
  composer.value = ""
}

function handleSuggestion(text: string) {
  composer.value = text
  emit("suggest", text)
}

function handleApprove() {
  approveOpen.value = false
  emit("approve")
}

function handleRevert() {
  revertOpen.value = false
  emit("revert")
}
</script>

<template>
  <!-- Organism raiz do Pipeline Editor V2 — sem composables/API, wiring externo via PR-C -->
  <div class="editor-root" :data-density="settings.density">

    <!-- ===================================================================
         Layout: tri_pane (padrão)
         =================================================================== -->
    <template v-if="settings.layout === 'tri_pane'">
      <div class="tri-pane-layout">
        <!-- Cabeçalho do workspace -->
        <EditorWorkspaceHeader
          :pipeline-name="pipelineName"
          :layer="layer"
          :target-node="targetNode"
          :target-table="targetTable"
          :mode="mode"
          :session="activeSession"
          @new-session="emit('newSession')"
          @share="shareOpen = true"
          @history="historyOpen = true"
          @help="shortcutsOpen = true"
        />

        <!-- Timeline de estado (opcional) -->
        <EditorStateTimeline
          v-if="settings.showStateTimeline"
          :current="stateMachine"
          :error="error?.message"
          @retry="emit('retry')"
        />

        <!-- Banner de erro global -->
        <EditorErrorBanner
          v-if="error"
          :error="error"
          @dismiss="emit('dismissError')"
          @retry="emit('retry')"
        />

        <!-- Corpo principal: rail + chat + inspector -->
        <div class="tri-body">
          <!-- Rail de sessões (opcional) -->
          <EditorSessionsRail
            v-if="settings.showSessionsRail"
            :sessions="sessions"
            :active-id="activeSessionId"
            :collapsed="sessionsCollapsed"
            @select="emit('update:activeSessionId', $event)"
            @new="emit('newSession')"
            @toggle="sessionsCollapsed = !sessionsCollapsed"
          />

          <!-- Painel de chat -->
          <div class="chat-pane">
            <EditorChatPane
              :messages="messages"
              :is-streaming="isStreaming"
              :source-of-truth="sourceOfTruth"
              :show-zero-state="messages.length === 0"
              @preview-proposal="emit('previewProposal')"
              @adjust-in-builder="emit('adjustInBuilder')"
              @apply-proposal="emit('applyProposal')"
              @suggestion="handleSuggestion"
            />

            <EditorComposer
              :model-value="composer"
              :disabled="isStreaming"
              :is-listening="listening"
              @update:model-value="composer = $event"
              @send="handleSend"
              @toggle-listen="listening = !listening"
            />
          </div>

          <!-- Painel do inspector -->
          <div class="inspector-pane">
            <EditorInspectorPane
              :inspector-tab="inspectorTab"
              :source-of-truth="sourceOfTruth"
              :draft="draft"
              :preview="preview"
              :running="previewRunning"
              :validation="validation"
              :session="activeSession"
              :proposal="proposal"
              :operations="draft?.operations || []"
              :file-diffs="fileDiffs"
              @update:inspector-tab="emit('update:inspectorTab', $event)"
              @update:draft="emit('update:draft', $event)"
              @mark-builder-active="emit('markBuilderActive')"
              @run-preview="emit('runPreview')"
              @export="emit('export', $event)"
              @approve="approveOpen = true"
              @share="shareOpen = true"
              @revert="revertOpen = true"
            />
          </div>
        </div>
      </div>
    </template>

    <!-- ===================================================================
         Layout: chat_dominant
         =================================================================== -->
    <template v-else-if="settings.layout === 'chat_dominant'">
      <div class="tri-pane-layout">
        <EditorWorkspaceHeader
          :pipeline-name="pipelineName"
          :layer="layer"
          :target-node="targetNode"
          :target-table="targetTable"
          :mode="mode"
          :session="activeSession"
          @new-session="emit('newSession')"
          @share="shareOpen = true"
          @history="historyOpen = true"
          @help="shortcutsOpen = true"
        />

        <EditorStateTimeline
          v-if="settings.showStateTimeline"
          :current="stateMachine"
          :error="error?.message"
          @retry="emit('retry')"
        />

        <EditorErrorBanner
          v-if="error"
          :error="error"
          @dismiss="emit('dismissError')"
          @retry="emit('retry')"
        />

        <div class="tri-body">
          <EditorSessionsRail
            v-if="settings.showSessionsRail"
            :sessions="sessions"
            :active-id="activeSessionId"
            :collapsed="sessionsCollapsed"
            @select="emit('update:activeSessionId', $event)"
            @new="emit('newSession')"
            @toggle="sessionsCollapsed = !sessionsCollapsed"
          />

          <!-- Chat dominante: flex-2 -->
          <div class="chat-pane chat-dominant">
            <EditorChatPane
              :messages="messages"
              :is-streaming="isStreaming"
              :source-of-truth="sourceOfTruth"
              :show-zero-state="messages.length === 0"
              @preview-proposal="emit('previewProposal')"
              @adjust-in-builder="emit('adjustInBuilder')"
              @apply-proposal="emit('applyProposal')"
              @suggestion="handleSuggestion"
            />
            <EditorComposer
              :model-value="composer"
              :disabled="isStreaming"
              :is-listening="listening"
              @update:model-value="composer = $event"
              @send="handleSend"
              @toggle-listen="listening = !listening"
            />
          </div>

          <!-- Inspector mais estreito -->
          <div class="inspector-pane inspector-narrow">
            <EditorInspectorPane
              :inspector-tab="inspectorTab"
              :source-of-truth="sourceOfTruth"
              :draft="draft"
              :preview="preview"
              :running="previewRunning"
              :validation="validation"
              :session="activeSession"
              :proposal="proposal"
              :operations="draft?.operations || []"
              :file-diffs="fileDiffs"
              @update:inspector-tab="emit('update:inspectorTab', $event)"
              @update:draft="emit('update:draft', $event)"
              @mark-builder-active="emit('markBuilderActive')"
              @run-preview="emit('runPreview')"
              @export="emit('export', $event)"
              @approve="approveOpen = true"
              @share="shareOpen = true"
              @revert="revertOpen = true"
            />
          </div>
        </div>
      </div>
    </template>

    <!-- ===================================================================
         Layout: conservative (V1+)
         =================================================================== -->
    <template v-else-if="settings.layout === 'conservative'">
      <div class="tri-pane-layout">
        <EditorWorkspaceHeader
          :pipeline-name="pipelineName"
          :layer="layer"
          :target-node="targetNode"
          :target-table="targetTable"
          :mode="mode"
          :session="activeSession"
          @new-session="emit('newSession')"
          @share="shareOpen = true"
          @history="historyOpen = true"
          @help="shortcutsOpen = true"
        />

        <EditorStateTimeline
          v-if="settings.showStateTimeline"
          :current="stateMachine"
          :error="error?.message"
          @retry="emit('retry')"
        />

        <EditorErrorBanner
          v-if="error"
          :error="error"
          @dismiss="emit('dismissError')"
          @retry="emit('retry')"
        />

        <div class="tri-body">
          <EditorSessionsRail
            v-if="settings.showSessionsRail"
            :sessions="sessions"
            :active-id="activeSessionId"
            :collapsed="sessionsCollapsed"
            @select="emit('update:activeSessionId', $event)"
            @new="emit('newSession')"
            @toggle="sessionsCollapsed = !sessionsCollapsed"
          />

          <div class="chat-pane">
            <EditorChatPane
              :messages="messages"
              :is-streaming="isStreaming"
              :source-of-truth="sourceOfTruth"
              :show-zero-state="messages.length === 0"
              @preview-proposal="emit('previewProposal')"
              @adjust-in-builder="emit('adjustInBuilder')"
              @apply-proposal="emit('applyProposal')"
              @suggestion="handleSuggestion"
            />
            <EditorComposer
              :model-value="composer"
              :disabled="isStreaming"
              :is-listening="listening"
              @update:model-value="composer = $event"
              @send="handleSend"
              @toggle-listen="listening = !listening"
            />
          </div>

          <!-- Inspector conservador: mais estreito que tri_pane -->
          <div class="inspector-pane inspector-conservative">
            <EditorInspectorPane
              :inspector-tab="inspectorTab"
              :source-of-truth="sourceOfTruth"
              :draft="draft"
              :preview="preview"
              :running="previewRunning"
              :validation="validation"
              :session="activeSession"
              :proposal="proposal"
              :operations="draft?.operations || []"
              :file-diffs="fileDiffs"
              @update:inspector-tab="emit('update:inspectorTab', $event)"
              @update:draft="emit('update:draft', $event)"
              @mark-builder-active="emit('markBuilderActive')"
              @run-preview="emit('runPreview')"
              @export="emit('export', $event)"
              @approve="approveOpen = true"
              @share="shareOpen = true"
              @revert="revertOpen = true"
            />
          </div>
        </div>
      </div>
    </template>

    <!-- ===================================================================
         Layout: wizard
         =================================================================== -->
    <template v-else-if="settings.layout === 'wizard'">
      <EditorWizardLayout
        :steps="['Chat', 'Builder', 'Preview', 'PR']"
        :current-step="wizardStep"
        @update:current-step="wizardStep = $event"
      >
        <!-- Chat -->
        <div v-if="wizardStep === 0" class="wizard-step-content">
          <EditorChatPane
            :messages="messages"
            :is-streaming="isStreaming"
            :source-of-truth="sourceOfTruth"
            :show-zero-state="messages.length === 0"
            @preview-proposal="emit('previewProposal')"
            @adjust-in-builder="emit('adjustInBuilder')"
            @apply-proposal="emit('applyProposal')"
            @suggestion="handleSuggestion"
          />
          <EditorComposer
            :model-value="composer"
            :disabled="isStreaming"
            :is-listening="listening"
            @update:model-value="composer = $event"
            @send="handleSend"
            @toggle-listen="listening = !listening"
          />
        </div>

        <!-- Builder -->
        <div v-else-if="wizardStep === 1" class="wizard-step-content">
          <EditorTransformBuilder
            :draft="draft"
            :source-of-truth="sourceOfTruth"
            @update:draft="emit('update:draft', $event)"
            @mark-builder-active="emit('markBuilderActive')"
          />
        </div>

        <!-- Preview -->
        <div v-else-if="wizardStep === 2" class="wizard-step-content">
          <EditorPreviewPanel
            :preview="preview"
            :running="previewRunning"
            @run-preview="emit('runPreview')"
            @export="emit('export', $event)"
          />
        </div>

        <!-- PR -->
        <div v-else-if="wizardStep === 3" class="wizard-step-content">
          <EditorPrPanel
            v-if="activeSession"
            :proposal="proposal"
            :preview="preview"
            :validation="validation"
            :session="activeSession"
            :file-diffs="fileDiffs"
            @approve="approveOpen = true"
            @share="shareOpen = true"
            @revert="revertOpen = true"
          />
        </div>
      </EditorWizardLayout>
    </template>

    <!-- ===================================================================
         Layout: tabbed (1 coluna)
         =================================================================== -->
    <template v-else-if="settings.layout === 'tabbed'">
      <EditorTabbedLayout
        :tabs="['Chat', 'Builder', 'Preview', 'PR']"
        :model-value="tabbedTab"
        @update:model-value="tabbedTab = $event"
      >
        <div v-if="tabbedTab === 'chat'" class="tabbed-step-content">
          <EditorChatPane
            :messages="messages"
            :is-streaming="isStreaming"
            :source-of-truth="sourceOfTruth"
            :show-zero-state="messages.length === 0"
            @preview-proposal="emit('previewProposal')"
            @adjust-in-builder="emit('adjustInBuilder')"
            @apply-proposal="emit('applyProposal')"
            @suggestion="handleSuggestion"
          />
          <EditorComposer
            :model-value="composer"
            :disabled="isStreaming"
            :is-listening="listening"
            @update:model-value="composer = $event"
            @send="handleSend"
            @toggle-listen="listening = !listening"
          />
        </div>

        <div v-else-if="tabbedTab === 'builder'" class="tabbed-step-content">
          <EditorTransformBuilder
            :draft="draft"
            :source-of-truth="sourceOfTruth"
            @update:draft="emit('update:draft', $event)"
            @mark-builder-active="emit('markBuilderActive')"
          />
        </div>

        <div v-else-if="tabbedTab === 'preview'" class="tabbed-step-content">
          <EditorPreviewPanel
            :preview="preview"
            :running="previewRunning"
            @run-preview="emit('runPreview')"
            @export="emit('export', $event)"
          />
        </div>

        <div v-else-if="tabbedTab === 'pr'" class="tabbed-step-content">
          <EditorPrPanel
            v-if="activeSession"
            :proposal="proposal"
            :preview="preview"
            :validation="validation"
            :session="activeSession"
            :file-diffs="fileDiffs"
            @approve="approveOpen = true"
            @share="shareOpen = true"
            @revert="revertOpen = true"
          />
        </div>
      </EditorTabbedLayout>
    </template>

    <!-- ===================================================================
         Modais — fora do conteúdo principal
         =================================================================== -->
    <EditorApproveModal
      :open="approveOpen"
      :session="activeSession"
      :proposal="proposal"
      :preview="preview"
      @close="approveOpen = false"
      @confirm="handleApprove"
    />

    <EditorShareModal
      :open="shareOpen"
      :session="activeSession"
      @close="shareOpen = false"
    />

    <EditorRevertModal
      :open="revertOpen"
      :session="activeSession"
      @close="revertOpen = false"
      @confirm="handleRevert"
    />

    <EditorShortcutSheet
      :open="shortcutsOpen"
      @close="shortcutsOpen = false"
    />

    <EditorHistoryView
      v-if="historyOpen"
      :sessions="sessions"
      @select="emit('update:activeSessionId', $event); historyOpen = false"
      @close="historyOpen = false"
    />
  </div>
</template>

<style scoped>
/* Raiz do editor — ocupa todo o espaço disponível */
.editor-root {
  display: flex;
  flex-direction: column;
  height: 100%;
  overflow: hidden;
  background: var(--bg);
  font-family: var(--font-sans);
}

/* Layout tri-pane base */
.tri-pane-layout {
  display: flex;
  flex-direction: column;
  height: 100%;
  overflow: hidden;
}

/* Corpo principal: rail + chat + inspector */
.tri-body {
  display: flex;
  flex-direction: row;
  flex: 1;
  min-height: 0;
  overflow: hidden;
}

/* Painel de chat */
.chat-pane {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  border-right: 1px solid var(--border);
}

/* Chat dominante ocupa mais espaço */
.chat-dominant {
  flex: 2;
}

/* Painel do inspector */
.inspector-pane {
  width: 400px;
  flex-shrink: 0;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

/* Inspector mais estreito para layout conservador */
.inspector-conservative {
  width: 320px;
}

/* Inspector mais estreito para layout chat_dominant */
.inspector-narrow {
  width: 320px;
}

/* Conteúdo de etapa no wizard */
.wizard-step-content {
  display: flex;
  flex-direction: column;
  height: 100%;
  overflow: hidden;
}

/* Conteúdo de aba no tabbed layout */
.tabbed-step-content {
  display: flex;
  flex-direction: column;
  height: 100%;
  overflow: hidden;
}

/* Ajustes de densidade */
.editor-root[data-density="compact"] {
  --editor-spacing: 6px;
  font-size: 12px;
}

.editor-root[data-density="comfortable"] {
  --editor-spacing: 10px;
  font-size: 13px;
}
</style>
