<template>
  <div class="grid grid-cols-1 xl:grid-cols-5 gap-4">
    <section class="xl:col-span-2 rounded-lg border p-4 flex flex-col gap-3" :style="{ borderColor: 'var(--border)' }">
      <div>
        <h2 class="text-sm font-semibold" :style="{ color: 'var(--text-primary)' }">
          Conversa de edição
        </h2>
        <p class="text-xs" :style="{ color: 'var(--text-tertiary)' }">
          Descreva mudanças na camada Silver (tabela ou coluna).
        </p>
      </div>

      <textarea
        v-model="message"
        class="min-h-32 rounded-md border bg-transparent p-3 text-sm"
        placeholder="Ex: na Silver, remova agent_notes e renomeie meta_city para cidade"
      />
      <div class="flex justify-end">
        <AppButton size="sm" :disabled="sending" @click="sendMessage">
          Gerar proposta
        </AppButton>
      </div>

      <ProposalDiffPanel :proposal="proposal" :code-diff="codeDiff" />
    </section>

    <section class="xl:col-span-3 space-y-4">
      <TransformBuilder :manifest="workspace.manifest" :draft="draft" @update="saveDraft" />
      <div class="flex flex-wrap gap-2 justify-end">
        <AppButton variant="outline" size="sm" :disabled="!sessionId" @click="runPreview">
          Testar preview
        </AppButton>
        <AppButton variant="outline" size="sm" :disabled="!sessionId" @click="loadPrompt">
          Extrair prompt.md
        </AppButton>
        <AppButton size="sm" :disabled="!sessionId" @click="approve">
          Aprovar e abrir PR
        </AppButton>
      </div>
      <DataPreviewGrid :preview="preview" @export="exportPreview" />
      <ApprovalTimeline
        :has-draft="draft.operations.length > 0"
        :has-preview="Boolean(preview)"
        :has-prompt="Boolean(promptMarkdown)"
        :approved="approved"
      />
      <section v-if="promptMarkdown" class="rounded-lg border p-4" :style="{ borderColor: 'var(--border)' }">
        <h3 class="text-sm font-semibold mb-2">prompt.md</h3>
        <pre class="max-h-80 overflow-auto text-xs whitespace-pre-wrap">{{ promptMarkdown }}</pre>
      </section>
    </section>
  </div>
</template>

<script setup lang="ts">
import type {
  CodeDiffFile,
  EditProposal,
  PipelineEditSession,
  PipelineWorkspace,
  TransformDraft,
} from "~/types/pipeline-editor"

const props = defineProps<{
  workspace: PipelineWorkspace
  sessions: PipelineEditSession[]
}>()

const api = usePipelinesApi()
const store = usePipelinesStore()

const firstNode = computed(() =>
  props.workspace.manifest.nodes.find((node) => node.layer === "silver")
    || props.workspace.manifest.nodes[0],
)

const sessionId = ref(props.sessions[0]?.id || "")
const message = ref("")
const sending = ref(false)
const proposal = ref<EditProposal | null>(null)
const codeDiff = ref<CodeDiffFile[] | null>(null)
const promptMarkdown = ref("")
const approved = ref(false)

const draft = ref<TransformDraft>({
  layer: (firstNode.value?.layer || "silver") as TransformDraft["layer"],
  targetNode: firstNode.value?.id || "silver_dedup",
  targetTable: firstNode.value?.outputTables[0] || "medallion.silver.messages_clean",
  operations: [],
  inputDataframe: "df_parsed",
  outputDataframe: "df_editor",
  warnings: [],
})

const preview = computed(() => store.preview)

async function ensureSession() {
  if (sessionId.value) return sessionId.value
  const session = await store.ensureEditSession(`Editor ${props.workspace.name}`)
  if (!session) throw new Error("Nao foi possivel criar sessao")
  sessionId.value = session.id
  return session.id
}

async function sendMessage() {
  if (!message.value.trim()) return
  sending.value = true
  try {
    const id = await ensureSession()
    const response = await api.sendEditMessage(
      props.workspace.id,
      id,
      message.value,
      draft.value,
    )
    proposal.value = response.proposal
    draft.value = response.proposal.draft
  } finally {
    sending.value = false
  }
}

async function saveDraft(nextDraft: TransformDraft) {
  draft.value = nextDraft
  await ensureSession()
  await store.saveDraft(nextDraft)
}

async function runPreview() {
  await ensureSession()
  await store.runPreview(50)
}

async function exportPreview(format: "csv" | "parquet") {
  const id = await ensureSession()
  await api.exportPreview(props.workspace.id, id, format)
}

async function loadPrompt() {
  const id = await ensureSession()
  const result = await api.getPromptMarkdown(props.workspace.id, id)
  promptMarkdown.value = result.content
}

async function approve() {
  const id = await ensureSession()
  const result = await api.approveEdit(props.workspace.id, id)
  codeDiff.value = result.diff || null
  approved.value = true
}
</script>
