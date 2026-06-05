<template>
  <div v-if="workspace" class="flex-1 flex flex-col overflow-hidden">
    <!-- ──────────────────────────────────────────────────────────────────
         Header da página (back-button + título + tabs):
         só aparece FORA da aba Editor. Na aba Editor o workspace é full-bleed
         e o próprio EditorWorkspaceHeader assume o topo (paridade c/ protótipo).
         ────────────────────────────────────────────────────────────────── -->
    <header v-if="activeTab !== 'edit'" class="px-8 py-4 border-b" :style="{ borderColor: 'var(--border)' }">
      <div class="flex items-center gap-3">
        <AppButton variant="ghost" size="sm" icon="i-heroicons-arrow-left" square to="/deployments" />

        <div class="flex-1 min-w-0">
          <h1 class="text-base font-semibold truncate" :style="{ color: 'var(--text-primary)' }">
            {{ workspace.name }}
          </h1>
          <p class="text-xs" :style="{ color: 'var(--text-tertiary)' }">
            Workspace tenant-scoped · {{ workspace.manifest.displayName }}
          </p>
        </div>
        <AppButton variant="outline" size="sm" icon="i-heroicons-chat-bubble-left-right" to="/chat">
          Chat geral
        </AppButton>
      </div>

      <nav class="flex gap-2 mt-4">
        <button
          v-for="tab in tabs"
          :key="tab.id"
          class="px-3 py-1.5 rounded-md text-xs"
          :class="{ 'font-semibold': activeTab === tab.id }"
          :style="tabStyle(tab.id)"
          @click="changeTab(tab.id)"
        >
          {{ tab.label }}
        </button>
      </nav>
    </header>

    <!-- ──────────────────────────────────────────────────────────────────
         Aba Editor (V2) — full-bleed, ocupa todo o viewport (sidebar global
         é ocultada via `editorFullBleed`). EditorWorkspaceHeader é o topo.
         ────────────────────────────────────────────────────────────────── -->
    <div v-if="activeTab === 'edit'" class="flex-1 min-h-0 overflow-hidden">
      <PipelineEditorV2
        :workspace="workspace"
        :sessions="sessions"
      />
    </div>

    <!-- ──────────────────────────────────────────────────────────────────
         Demais abas — dentro do <main> com padding
         ────────────────────────────────────────────────────────────────── -->
    <main v-else class="flex-1 overflow-auto p-6">
      <!-- Overview -->
      <section v-if="activeTab === 'overview'" class="grid grid-cols-1 md:grid-cols-3 gap-4">
        <MetricCard
          label="Job Databricks"
          icon="circle-stack"
          :value="workspace.databricksJobId ? String(workspace.databricksJobId) : 'Não configurado'"
        />
        <MetricCard label="Nós editáveis" icon="code-bracket" :value="String(workspace.manifest.nodes.length)" />
        <MetricCard label="Sessões" icon="chat-bubble-left-right" :value="String(sessions.length)" />
      </section>

      <!-- Dados -->
      <DataPreviewGrid
        v-else-if="activeTab === 'data'"
        :preview="preview"
        @export="exportPreview"
      />

      <!-- Diagrama -->
      <PipelineDiagram
        v-else-if="activeTab === 'diagram'"
        :manifest="workspace.manifest"
        :draft="activeDraft"
      />

      <!-- Histórico — usa EditorHistoryView (RF-15) -->
      <EditorHistoryView
        v-else-if="activeTab === 'history'"
        :sessions="sessions"
        @select="onHistorySelect"
        @close="activeTab = 'edit'"
      />
    </main>
  </div>

  <EmptyState
    v-else
    icon="face-frown"
    title="Pipeline não encontrado"
    description="Esse pipeline pode ter sido removido ou você não tem acesso ao tenant."
    class="flex-1"
  />
</template>

<script setup lang="ts">
import type { TransformDraft } from "~/types/pipeline-editor"

definePageMeta({ layout: "default" })

const route = useRoute()
const store = usePipelinesStore()
const api = usePipelinesApi()

const pipelineId = computed(() => String(route.params.id))

// Editor é a aba padrão ao abrir o pipeline (V2)
const activeTab = ref("edit")

function changeTab(id: string) {
  activeTab.value = id
}

// Exposto para navegação programática (testes / controles externos).
defineExpose({ changeTab })

// Full-bleed: na aba Editor a sidebar global é ocultada (paridade c/ protótipo).
const editorFullBleed = useState("editorFullBleed", () => false)
watchEffect(() => {
  editorFullBleed.value = activeTab.value === "edit"
})
onBeforeUnmount(() => {
  editorFullBleed.value = false
})

const tabs = [
  { id: "edit", label: "Editor" },
  { id: "overview", label: "Overview" },
  { id: "data", label: "Dados" },
  { id: "diagram", label: "Diagrama" },
  { id: "history", label: "Histórico" },
]

await store.load()
await store.loadWorkspace(pipelineId.value)

const workspace = computed(() => store.workspace)
const sessions = computed(() => store.editSessions)
const preview = computed(() => store.preview)
const activeDraft = computed<TransformDraft | null>(() => store.activeDraft)

function tabStyle(id: string) {
  if (activeTab.value === id) {
    return {
      background: "var(--brand-600)",
      color: "white",
    }
  }
  return {
    background: "var(--surface-muted)",
    color: "var(--text-secondary)",
  }
}

async function exportPreview(format: "csv" | "parquet") {
  const sessionId = store.activeEditSessionId || sessions.value[0]?.id
  if (!workspace.value || !sessionId) return
  await api.exportPreview(workspace.value.id, sessionId, format)
}

// Histórico: seleciona sessão e volta para aba edit
function onHistorySelect(id: string) {
  store.setActiveEditSession(id)
  activeTab.value = "edit"
}
</script>
