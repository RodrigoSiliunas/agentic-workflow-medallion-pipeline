<template>
  <section class="rounded-lg border p-4 space-y-4" :style="{ borderColor: 'var(--border)' }">
    <div class="flex items-center justify-between gap-3">
      <div>
        <h3 class="text-sm font-semibold" :style="{ color: 'var(--text-primary)' }">
          Preview dos dados
        </h3>
        <p class="text-xs" :style="{ color: 'var(--text-tertiary)' }">
          Namespace: {{ preview?.namespace || "preview ainda não executado" }}
        </p>
      </div>
      <PreviewExportMenu :disabled="!preview" @export="emit('export', $event)" />
    </div>

    <div v-if="preview" class="grid grid-cols-1 md:grid-cols-3 gap-3">
      <MetricCard label="Status" icon="check-circle" :value="String(preview.status || 'ready')" />
      <MetricCard label="Sample" icon="table-cells" :value="`${preview.sample_rows || 0} linhas`" />
      <MetricCard label="Tabela alvo" icon="circle-stack" :value="String(preview.target_table || '-')" />
    </div>

    <div v-if="schemaDelta" class="grid grid-cols-1 md:grid-cols-3 gap-3 text-xs">
      <div class="rounded-md border p-3" :style="{ borderColor: 'var(--border)' }">
        <strong>Removidas</strong>
        <p :style="{ color: 'var(--text-tertiary)' }">{{ schemaDelta.dropped.join(", ") || "-" }}</p>
      </div>
      <div class="rounded-md border p-3" :style="{ borderColor: 'var(--border)' }">
        <strong>Renomeadas</strong>
        <p :style="{ color: 'var(--text-tertiary)' }">{{ renamedText || "-" }}</p>
      </div>
      <div class="rounded-md border p-3" :style="{ borderColor: 'var(--border)' }">
        <strong>Derivadas</strong>
        <p :style="{ color: 'var(--text-tertiary)' }">{{ schemaDelta.derived.join(", ") || "-" }}</p>
      </div>
    </div>

    <div v-if="!preview" class="text-xs py-10 text-center" :style="{ color: 'var(--text-tertiary)' }">
      Execute o preview para validar schema e amostra antes de aprovar o PR.
    </div>
  </section>
</template>

<script setup lang="ts">
const props = defineProps<{
  preview: Record<string, unknown> | null
}>()

const emit = defineEmits<{
  export: [format: "csv" | "parquet"]
}>()

const schemaDelta = computed(() => props.preview?.schema_delta as {
  dropped: string[]
  renamed: Array<{ from: string; to: string }>
  derived: string[]
} | undefined)

const renamedText = computed(() =>
  schemaDelta.value?.renamed.map((item) => `${item.from} -> ${item.to}`).join(", "),
)
</script>
