<template>
  <section class="rounded-lg border p-4 space-y-3" :style="{ borderColor: 'var(--border)' }">
    <div class="flex items-center justify-between">
      <div>
        <h3 class="text-sm font-semibold" :style="{ color: 'var(--text-primary)' }">
          Diagrama do pipeline
        </h3>
        <p class="text-xs" :style="{ color: 'var(--text-tertiary)' }">
          Mermaid exportável para revisão externa.
        </p>
      </div>
      <AppButton variant="outline" size="sm" @click="copyDiagram">
        Copiar Mermaid
      </AppButton>
    </div>
    <pre class="overflow-x-auto rounded-md border p-3 text-xs" :style="{ borderColor: 'var(--border)' }">{{ diagram }}</pre>
  </section>
</template>

<script setup lang="ts">
import type { PipelineManifest, TransformDraft } from "~/types/pipeline-editor"

const props = defineProps<{
  manifest: PipelineManifest
  draft: TransformDraft | null
}>()

const diagram = computed(() => {
  const silverNodes = props.manifest.nodes.filter((node) => node.layer === "silver")
  const lines = ["flowchart LR"]
  silverNodes.forEach((node) => {
    lines.push(`  ${node.id}["${node.layer}: ${node.taskKey}"]`)
  })
  for (let index = 1; index < silverNodes.length; index += 1) {
    lines.push(`  ${silverNodes[index - 1].id} --> ${silverNodes[index].id}`)
  }
  if (props.draft) {
    lines.push(`  draft["Draft: ${props.draft.operations.length} ops"] --> ${props.draft.targetNode}`)
  }
  return lines.join("\n")
})

async function copyDiagram() {
  await navigator.clipboard?.writeText(diagram.value)
}
</script>
