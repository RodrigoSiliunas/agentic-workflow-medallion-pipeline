<template>
  <section class="flex flex-col gap-4">
    <div class="grid grid-cols-1 md:grid-cols-3 gap-3">
      <label class="flex flex-col gap-1 text-xs">
        <span :style="{ color: 'var(--text-tertiary)' }">Camada</span>
        <input
          value="Silver"
          disabled
          class="rounded-md border px-3 py-2 bg-transparent opacity-80"
        >
      </label>

      <label class="flex flex-col gap-1 text-xs md:col-span-2">
        <span :style="{ color: 'var(--text-tertiary)' }">Nó editável (Silver)</span>
        <select v-model="localDraft.targetNode" class="rounded-md border px-3 py-2 bg-transparent" @change="syncNode">
          <option v-for="node in layerNodes" :key="node.id" :value="node.id">
            {{ node.taskKey }} · {{ node.filePath }}
          </option>
        </select>
      </label>
    </div>

    <p class="text-xs" :style="{ color: 'var(--text-tertiary)' }">
      Bronze e Gold ficam fora do escopo desta fase — apenas transformações Silver.
    </p>

    <div class="rounded-lg border p-4 space-y-3" :style="{ borderColor: 'var(--border)' }">
      <div class="flex items-center justify-between gap-3">
        <div>
          <h3 class="text-sm font-semibold" :style="{ color: 'var(--text-primary)' }">
            Operações low-code
          </h3>
          <p class="text-xs" :style="{ color: 'var(--text-tertiary)' }">
            Chat e builder escrevem o mesmo DSL versionado.
          </p>
        </div>
        <AppButton size="sm" icon="i-heroicons-plus" @click="addOperation">
          Adicionar
        </AppButton>
      </div>

      <div v-if="localDraft.operations.length === 0" class="text-xs py-6 text-center" :style="{ color: 'var(--text-tertiary)' }">
        Nenhuma operação adicionada.
      </div>

      <div
        v-for="(operation, index) in localDraft.operations"
        :key="index"
        class="grid grid-cols-1 md:grid-cols-12 gap-2 items-end rounded-md border p-3"
        :style="{ borderColor: 'var(--border)' }"
      >
        <label class="md:col-span-3 flex flex-col gap-1 text-xs">
          <span :style="{ color: 'var(--text-tertiary)' }">Operação</span>
          <select v-model="operation.op" class="rounded-md border px-2 py-2 bg-transparent">
            <option value="drop_column">Remover coluna</option>
            <option value="rename_column">Renomear coluna</option>
            <option value="cast_column">Alterar tipo</option>
            <option value="trim">Trim</option>
            <option value="regex_replace">Regex replace</option>
            <option value="derive_column">Coluna derivada</option>
            <option value="filter_rows">Filtrar linhas</option>
            <option value="json_extract">Extrair JSON</option>
            <option value="mask_pii">Mascarar PII</option>
          </select>
        </label>

        <label class="md:col-span-2 flex flex-col gap-1 text-xs">
          <span :style="{ color: 'var(--text-tertiary)' }">Coluna</span>
          <input v-model="operation.column" class="rounded-md border px-2 py-2 bg-transparent" placeholder="sender_name">
        </label>

        <label class="md:col-span-2 flex flex-col gap-1 text-xs">
          <span :style="{ color: 'var(--text-tertiary)' }">Novo nome/tipo</span>
          <input v-model="operation.newName" class="rounded-md border px-2 py-2 bg-transparent" placeholder="cidade">
        </label>

        <label class="md:col-span-3 flex flex-col gap-1 text-xs">
          <span :style="{ color: 'var(--text-tertiary)' }">Expressão / padrão</span>
          <input v-model="operation.expression" class="rounded-md border px-2 py-2 bg-transparent" placeholder="F.col('x')">
        </label>

        <AppButton
          class="md:col-span-2"
          variant="ghost"
          size="sm"
          color="error"
          icon="i-heroicons-trash"
          @click="removeOperation(index)"
        >
          Remover
        </AppButton>
      </div>
    </div>

    <div class="flex justify-end gap-2">
      <AppButton variant="outline" size="sm" @click="emitUpdate">
        Salvar draft
      </AppButton>
    </div>
  </section>
</template>

<script setup lang="ts">
import type { PipelineManifest, TransformDraft } from "~/types/pipeline-editor"

const props = defineProps<{
  manifest: PipelineManifest
  draft: TransformDraft
}>()

const emit = defineEmits<{
  update: [draft: TransformDraft]
}>()

const localDraft = reactive<TransformDraft>(structuredClone(props.draft))

watch(
  () => localDraft.layer,
  (layer) => {
    if (layer !== "silver") {
      localDraft.layer = "silver"
    }
  },
)

const layerNodes = computed(() =>
  props.manifest.nodes.filter((node) => node.layer === "silver"),
)

watch(() => props.draft, (draft) => {
  Object.assign(localDraft, structuredClone(draft))
})

function syncNode() {
  const node = props.manifest.nodes.find((item) => item.id === localDraft.targetNode)
  if (node?.outputTables[0]) localDraft.targetTable = node.outputTables[0]
}

function addOperation() {
  localDraft.operations.push({
    op: "trim",
    column: "",
    sourceColumns: [],
    params: {},
  })
}

function removeOperation(index: number) {
  localDraft.operations.splice(index, 1)
}

function emitUpdate() {
  emit("update", structuredClone(localDraft))
}
</script>
