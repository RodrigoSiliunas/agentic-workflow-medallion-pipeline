<template>
  <section class="rounded-lg border p-4 space-y-3" :style="{ borderColor: 'var(--border)' }">
    <div>
      <h3 class="text-sm font-semibold" :style="{ color: 'var(--text-primary)' }">
        Proposta estruturada
      </h3>
      <p class="text-xs" :style="{ color: 'var(--text-tertiary)' }">
        {{ proposal?.explanation || "Aguardando proposta do chat ou builder." }}
      </p>
    </div>

    <div v-if="proposal" class="space-y-2">
      <div class="text-xs">
        <strong>Risco:</strong> {{ proposal.riskScore }}/10
      </div>
      <div class="text-xs">
        <strong>Arquivos:</strong> {{ proposal.filesAffected.join(", ") || "-" }}
      </div>
      <ol class="text-xs space-y-1 list-decimal list-inside" :style="{ color: 'var(--text-secondary)' }">
        <li v-for="operation in proposal.draft.operations" :key="operation.op + operation.column">
          {{ operation.op }} · {{ operation.column || operation.expression || "pipeline" }}
        </li>
      </ol>
    </div>

    <div v-if="codeDiff?.length" class="space-y-3">
      <h4 class="text-xs font-semibold" :style="{ color: 'var(--text-primary)' }">
        Diff de código
      </h4>
      <article
        v-for="file in codeDiff"
        :key="file.path"
        class="rounded-md border overflow-hidden"
        :style="{ borderColor: 'var(--border)' }"
      >
        <header class="px-3 py-2 text-xs font-medium border-b" :style="{ borderColor: 'var(--border)' }">
          {{ file.path }}
          <span class="ml-2" :style="{ color: 'var(--text-tertiary)' }">
            +{{ file.additions }} / -{{ file.deletions }}
          </span>
        </header>
        <pre
          class="max-h-64 overflow-auto p-3 text-[11px] leading-relaxed whitespace-pre-wrap"
          :style="{ color: 'var(--text-secondary)' }"
        >{{ file.patch || "Sem alterações visíveis." }}</pre>
      </article>
    </div>
  </section>
</template>

<script setup lang="ts">
import type { CodeDiffFile, EditProposal } from "~/types/pipeline-editor"

defineProps<{
  proposal: EditProposal | null
  codeDiff?: CodeDiffFile[] | null
}>()
</script>
