<template>
  <div v-if="workspace" class="flex-1 flex flex-col overflow-hidden">
    <header class="px-8 py-4 border-b" :style="{ borderColor: 'var(--border)' }">
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
          @click="activeTab = tab.id"
        >
          {{ tab.label }}
        </button>
      </nav>
    </header>

    <main class="flex-1 overflow-auto p-6">
      <section v-if="activeTab === 'overview'" class="grid grid-cols-1 md:grid-cols-3 gap-4">
        <MetricCard
          label="Job Databricks"
          icon="circle-stack"
          :value="workspace.databricksJobId ? String(workspace.databricksJobId) : 'Não configurado'"
        />
        <MetricCard label="Nós editáveis" icon="code-bracket" :value="String(workspace.manifest.nodes.length)" />
        <MetricCard label="Sessões" icon="chat-bubble-left-right" :value="String(sessions.length)" />
      </section>

      <PipelineEditorWorkspace
        v-else-if="activeTab === 'edit'"
        :workspace="workspace"
        :sessions="sessions"
      />

      <DataPreviewGrid
        v-else-if="activeTab === 'data'"
        :preview="preview"
        @export="exportPreview"
      />

      <PipelineDiagram
        v-else-if="activeTab === 'diagram'"
        :manifest="workspace.manifest"
        :draft="activeDraft"
      />

      <section v-else class="space-y-3">
        <h2 class="text-sm font-semibold">Histórico de edição</h2>
        <div
          v-for="session in sessions"
          :key="session.id"
          class="rounded-lg border p-4"
          :style="{ borderColor: 'var(--border)' }"
        >
          <p class="text-sm font-medium">{{ session.title }}</p>
          <p class="text-xs" :style="{ color: 'var(--text-tertiary)' }">
            {{ session.status }} · {{ session.updatedAt || session.createdAt || "-" }}
          </p>
        </div>
      </section>
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
const activeTab = ref("overview")

const tabs = [
  { id: "overview", label: "Overview" },
  { id: "edit", label: "Editar" },
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
</script>
