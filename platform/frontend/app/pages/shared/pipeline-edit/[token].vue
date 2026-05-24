<template>
  <div v-if="shared" class="flex-1 flex flex-col overflow-hidden">
    <header class="px-8 py-4 border-b" :style="{ borderColor: 'var(--border)' }">
      <div class="flex items-center gap-3">
        <div class="flex-1 min-w-0">
          <p class="text-xs uppercase tracking-wide" :style="{ color: 'var(--text-tertiary)' }">
            Visualização compartilhada · somente leitura
          </p>
          <h1 class="text-base font-semibold truncate" :style="{ color: 'var(--text-primary)' }">
            {{ shared.pipeline.name }}
          </h1>
          <p v-if="shared.session?.title" class="text-xs" :style="{ color: 'var(--text-tertiary)' }">
            {{ shared.session.title }} · {{ shared.session.status }}
          </p>
        </div>
      </div>
    </header>

    <main class="flex-1 overflow-auto p-6 space-y-4">
      <DataPreviewGrid :preview="shared.preview" />
      <PipelineDiagram
        v-if="shared.manifest"
        :manifest="shared.manifest"
        :draft="shared.draft"
      />
      <section
        v-if="shared.promptMarkdown"
        class="rounded-lg border p-4"
        :style="{ borderColor: 'var(--border)' }"
      >
        <h3 class="text-sm font-semibold mb-2">prompt.md</h3>
        <pre class="max-h-80 overflow-auto text-xs whitespace-pre-wrap">{{ shared.promptMarkdown }}</pre>
      </section>
    </main>
  </div>

  <EmptyState
    v-else-if="errorMessage"
    icon="face-frown"
    title="Link indisponível"
    :description="errorMessage"
    class="flex-1"
  />

  <div v-else class="flex-1 flex items-center justify-center text-sm" :style="{ color: 'var(--text-tertiary)' }">
    Carregando compartilhamento...
  </div>
</template>

<script setup lang="ts">
import type { PipelineManifest, TransformDraft } from "~/types/pipeline-editor"

definePageMeta({ layout: "default" })

interface SharedPipelineEdit {
  role: string
  readOnly: boolean
  pipeline: { id: string; name: string; description: string | null }
  session: { id: string | null; title: string | null; status: string | null } | null
  manifest: PipelineManifest | null
  draft: TransformDraft | null
  preview: Record<string, unknown> | null
  promptMarkdown: string | null
}

const route = useRoute()
const api = usePipelinesApi()

const shared = ref<SharedPipelineEdit | null>(null)
const errorMessage = ref("")

function toManifest(raw: Record<string, unknown>): PipelineManifest {
  return {
    templateSlug: String(raw.template_slug),
    displayName: String(raw.display_name),
    nodes: ((raw.nodes as Record<string, unknown>[] | undefined) || []).map((node) => ({
      id: String(node.id),
      layer: node.layer as PipelineManifest["nodes"][number]["layer"],
      taskKey: String(node.task_key),
      filePath: String(node.file_path),
      inputTables: (node.input_tables as string[] | undefined) || [],
      outputTables: (node.output_tables as string[] | undefined) || [],
      supportedOperations: (node.supported_operations as string[] | undefined) || [],
      insertionMarker: String(node.insertion_marker),
    })),
  }
}

function toDraft(raw: Record<string, unknown> | null): TransformDraft | null {
  if (!raw) return null
  return {
    layer: raw.layer as TransformDraft["layer"],
    targetNode: String(raw.target_node ?? raw.targetNode ?? ""),
    targetTable: String(raw.target_table ?? raw.targetTable ?? ""),
    operations: ((raw.operations as Record<string, unknown>[] | undefined) || []).map((op) => ({
      op: String(op.op),
      column: op.column as string | null | undefined,
      newName: op.new_name as string | null | undefined,
    })),
  }
}

try {
  const token = String(route.params.token)
  const data = await api.getSharedPipelineEdit(token)
  shared.value = {
    role: String(data.role),
    readOnly: Boolean(data.read_only),
    pipeline: data.pipeline as SharedPipelineEdit["pipeline"],
    session: (data.session as SharedPipelineEdit["session"]) || null,
    manifest: data.manifest ? toManifest(data.manifest as Record<string, unknown>) : null,
    draft: toDraft(data.draft as Record<string, unknown> | null),
    preview: (data.preview as Record<string, unknown> | null) || null,
    promptMarkdown: (data.prompt_markdown as string | null) || null,
  }
} catch (error) {
  errorMessage.value = error instanceof Error ? error.message : "Não foi possível carregar o link."
}
</script>
