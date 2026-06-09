<template>
  <div class="flex h-full min-h-0 flex-col overflow-hidden">
    <!-- Abas do inspector -->
    <div
      class="flex-shrink-0 border-b border-[var(--border)] px-[10px] pt-[8px]"
      :style="inspectorTab === 'rascunho' && sourceOfTruth === 'builder'
        ? { background: 'rgba(142,81,246,0.04)' }
        : {}"
    >
      <EditorTabs
        :model-value="inspectorTab"
        :tabs="[
          { id: 'rascunho', label: 'Rascunho', icon: 'pencil-square', count: operations.length },
          { id: 'preview',  label: 'Preview',  icon: 'play' },
          { id: 'pr',       label: 'PR',        icon: 'code-bracket' },
        ]"
        size="sm"
        @update:model-value="emit('update:inspectorTab', $event as InspectorTab)"
      />
    </div>

    <!-- Painel da aba Rascunho -->
    <div v-if="inspectorTab === 'rascunho'" class="min-h-0 flex-1 overflow-hidden">
      <EditorTransformBuilder
        :draft="draft"
        :source-of-truth="sourceOfTruth"
        :auto-saved-at="null"
        :table-columns="tableColumns"
        @update:draft="emit('update:draft', $event)"
        @mark-active="emit('markBuilderActive')"
      />
    </div>

    <!-- Painel da aba Preview -->
    <div v-else-if="inspectorTab === 'preview'" class="min-h-0 flex-1 overflow-hidden">
      <EditorPreviewPanel
        :preview="preview"
        :running="running"
        :operations="operations"
        @run="emit('runPreview')"
        @export="emit('export', $event)"
      />
    </div>

    <!-- Painel da aba PR -->
    <div v-else-if="inspectorTab === 'pr'" class="min-h-0 flex-1 overflow-hidden">
      <EditorPrPanel
        :proposal="proposal"
        :preview="preview"
        :validation="validation"
        :session="session"
        :file-diffs="fileDiffs"
        @approve="emit('approve')"
        @share="emit('share')"
        @revert="emit('revert')"
      />
    </div>
  </div>
</template>

<script setup lang="ts">
import type {
  InspectorTab,
  SourceOfTruth,
  TransformDraft,
  TransformOperation,
  PreviewResultV2,
  ValidationResult,
  PipelineEditSession,
  EditProposal,
  FileDiff,
  SchemaColumn,
} from "~/types/pipeline-editor-v2"

withDefaults(
  defineProps<{
    inspectorTab?: InspectorTab
    sourceOfTruth?: SourceOfTruth
    draft?: TransformDraft | null
    preview?: PreviewResultV2 | null
    running?: boolean
    validation?: ValidationResult | null
    session?: PipelineEditSession | null
    proposal?: EditProposal | null
    operations?: TransformOperation[]
    fileDiffs?: FileDiff[]
    tableColumns?: SchemaColumn[]
  }>(),
  {
    inspectorTab: "rascunho",
    sourceOfTruth: null,
    draft: null,
    preview: null,
    running: false,
    validation: null,
    session: null,
    proposal: null,
    operations: () => [],
    fileDiffs: () => [],
    tableColumns: () => [],
  },
)

const emit = defineEmits<{
  "update:inspectorTab": [tab: InspectorTab]
  "update:draft": [draft: TransformDraft]
  markBuilderActive: []
  runPreview: []
  export: [format: string]
  approve: []
  share: []
  revert: []
}>()
</script>
