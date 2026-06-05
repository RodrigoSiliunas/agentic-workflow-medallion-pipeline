<template>
  <div class="flex h-full flex-col overflow-hidden">
    <!-- Estado zero: sem preview e não está rodando -->
    <div
      v-if="!preview && !running"
      class="flex h-full flex-col items-center justify-center gap-[16px] p-[32px] text-center"
    >
      <div
        class="flex h-[48px] w-[48px] items-center justify-center rounded-[var(--radius-lg)]"
        style="background: rgba(142, 81, 246, 0.1)"
      >
        <AppIcon name="play" size="lg" :style="{ color: 'var(--brand-400)' }" />
      </div>
      <div class="flex flex-col gap-[6px]">
        <p class="text-[14px] font-semibold" :style="{ color: 'var(--fg-primary)' }">
          Nenhum preview executado ainda
        </p>
        <p class="max-w-[280px] text-[12px]" :style="{ color: 'var(--fg-tertiary)' }">
          Execute o preview para ver o resultado das transformações aplicadas ao dataset.
        </p>
      </div>
      <AppButton
        variant="solid"
        color="primary"
        size="md"
        icon="play"
        @click="emit('run')"
      >
        Rodar preview agora
      </AppButton>
      <span class="text-[11px]" :style="{ color: 'var(--fg-tertiary)' }">≈ 30–60s</span>
    </div>

    <!-- Estado de carregamento -->
    <div v-else-if="running" class="flex flex-col gap-[12px] p-[14px]">
      <SectionHeader overline="Preview" title="Executando transformações…" />
      <EditorPreviewSkeleton />
    </div>

    <!-- Preview disponível -->
    <div v-else class="flex flex-col gap-[16px] overflow-y-auto p-[14px]">
      <!-- Barra de status do preview -->
      <div
        class="flex flex-wrap items-center gap-[8px] rounded-[var(--radius-lg)] border border-[var(--border)] bg-[var(--surface)] px-[12px] py-[10px]"
      >
        <AppPill tone="success" size="xs" dot icon="check-circle">Pronto</AppPill>
        <AppCode class="font-mono text-[11px]">preview-ns</AppCode>
        <AppPill tone="neutral" size="xs" icon="clock">~42s</AppPill>
        <div class="flex-1" />
        <AppButton
          variant="ghost"
          color="neutral"
          size="sm"
          icon="arrow-down-tray"
          @click="emit('export', 'csv')"
        >
          Exportar
        </AppButton>
        <AppButton
          variant="ghost"
          color="neutral"
          size="sm"
          icon="arrow-path"
          @click="emit('run')"
        >
          Re-rodar
        </AppButton>
      </div>

      <!-- Seção: passos da transformação -->
      <div class="flex flex-col gap-[8px]">
        <SectionHeader overline="Transformação" :title="`${builtSteps.length} passo${builtSteps.length !== 1 ? 's' : ''}`" />
        <div
          v-if="builtSteps.length === 0"
          class="rounded-[var(--radius-md)] border border-dashed border-[var(--border)] px-[12px] py-[16px] text-center text-[12px]"
          :style="{ color: 'var(--fg-tertiary)' }"
        >
          Nenhuma operação definida
        </div>
        <TransformStepRow
          v-for="(step, i) in builtSteps"
          :key="i"
          :index="i"
          :kind="step.kind"
          :column="step.column"
          :from-column="step.fromColumn"
          :to-column="step.toColumn"
          :expression="step.expression"
          :cast-type="step.castType"
          :params="step.params"
          :note="step.note"
        />
      </div>

      <!-- Seção: schema resultante -->
      <div class="flex flex-col gap-[8px]">
        <SectionHeader overline="Schema" title="Colunas resultantes">
          <template #action>
            <KebabMenu
              :items="[
                { icon: 'arrow-down-tray', label: 'Exportar schema JSON', onClick: () => emit('export', 'json') },
                { icon: 'arrows-pointing-out', label: 'Expandir schema', onClick: () => (schemaExpandOpen = true) },
              ]"
            />
          </template>
        </SectionHeader>

        <!-- Cabeçalho da tabela de schema -->
        <div
          class="grid text-[10px] font-semibold uppercase tracking-[0.06em]"
          style="grid-template-columns: 1.6fr 1.2fr 0.7fr 1.3fr; padding: 4px 12px"
          :style="{ color: 'var(--fg-tertiary)' }"
        >
          <span>Nome</span>
          <span>Tipo</span>
          <span>Nullable</span>
          <span>Estado</span>
        </div>

        <div
          class="overflow-hidden rounded-[var(--radius-md)] border border-[var(--border)]"
        >
          <SchemaColumnRow
            v-for="(col, i) in allSchemaColumns"
            :key="col.name"
            :column="col"
            :border-top="i > 0"
            dense
          />
        </div>
      </div>

      <!-- Seção: dados resultantes (primeiras 50 linhas) -->
      <div class="flex flex-col gap-[8px]">
        <SectionHeader overline="Dados" title="Primeiras 50 linhas">
          <template #action>
            <div class="flex items-center gap-[6px]">
              <AppButton
                variant="ghost"
                color="neutral"
                size="sm"
                icon="squares-2x2"
                @click="compareOpen = true"
              >
                Comparar
              </AppButton>
              <KebabMenu
                :items="[
                  { icon: 'arrow-down-tray', label: 'Exportar CSV', onClick: () => emit('export', 'csv') },
                  { icon: 'arrow-down-tray', label: 'Exportar Parquet', onClick: () => emit('export', 'parquet') },
                  { icon: 'arrow-down-tray', label: 'Exportar JSON', onClick: () => emit('export', 'json') },
                  { icon: 'arrows-pointing-out', label: 'Expandir tabela', onClick: () => (dataExpandOpen = true) },
                ]"
              />
            </div>
          </template>
        </SectionHeader>

        <EditorResultTable
          :rows="preview?.rowsAfter ?? []"
          :schema-delta="preview?.schemaDelta ?? null"
          label="Depois"
          tone="success"
          max-height="320px"
        />
      </div>
    </div>

    <!-- Modal expandido do schema -->
    <EditorExpandedTableModal
      :open="schemaExpandOpen"
      title="Schema resultante"
      :on-export="() => emit('export', 'json')"
      @close="schemaExpandOpen = false"
    >
      <div class="overflow-hidden rounded-[var(--radius-md)] border border-[var(--border)]">
        <SchemaColumnRow
          v-for="(col, i) in allSchemaColumns"
          :key="col.name"
          :column="col"
          :border-top="i > 0"
        />
      </div>
    </EditorExpandedTableModal>

    <!-- Modal expandido dos dados -->
    <EditorExpandedTableModal
      :open="dataExpandOpen"
      title="Dados resultantes"
      :on-export="() => emit('export', 'csv')"
      @close="dataExpandOpen = false"
    >
      <EditorResultTable
        :rows="preview?.rowsAfter ?? []"
        :schema-delta="preview?.schemaDelta ?? null"
        label="Depois"
        tone="success"
      />
    </EditorExpandedTableModal>

    <!-- Modal de comparação antes/depois -->
    <EditorComparisonModal
      :open="compareOpen"
      :preview="preview"
      :on-export="() => emit('export', 'csv')"
      @close="compareOpen = false"
    />
  </div>
</template>

<script setup lang="ts">
import type { PreviewResultV2, SchemaDelta, SchemaColumn, TransformOperation } from "~/types/pipeline-editor-v2"
import type { TransformStepKind } from "~/components/molecules/TransformStepRow.vue"

const props = withDefaults(
  defineProps<{
    preview?: PreviewResultV2 | null
    running?: boolean
    operations?: TransformOperation[]
  }>(),
  {
    preview: null,
    running: false,
    operations: () => [],
  },
)

const emit = defineEmits<{
  run: []
  export: [format: string]
}>()

// Estado dos modais
const schemaExpandOpen = ref(false)
const dataExpandOpen = ref(false)
const compareOpen = ref(false)

// Colunas de schema incluindo removidas do delta
const allSchemaColumns = computed<SchemaColumn[]>(() => {
  const after = props.preview?.schemaAfter ?? []
  const removed = props.preview?.schemaDelta?.removed ?? []

  const removedCols: SchemaColumn[] = removed
    .filter((name) => !after.some((c) => c.name === name))
    .map((name) => ({
      name,
      type: "—",
      state: "removed" as const,
    }))

  return [...after, ...removedCols]
})

// Constrói lista de passos a partir do schemaDelta + operações
interface BuildStep {
  kind: TransformStepKind
  column?: string
  fromColumn?: string
  toColumn?: string
  expression?: string
  castType?: string
  params?: string
  note?: string
}

function buildSteps(delta: SchemaDelta | undefined, ops: TransformOperation[]): BuildStep[] {
  const steps: BuildStep[] = []

  // Passos derivados do schemaDelta
  if (delta) {
    for (const r of delta.renamed ?? []) {
      steps.push({ kind: "renamed", fromColumn: r.from, toColumn: r.to })
    }
    for (const name of delta.removed ?? []) {
      steps.push({ kind: "removed", column: name })
    }
    for (const d of delta.derived ?? []) {
      if (typeof d === "string") {
        steps.push({ kind: "derived", column: d })
      } else {
        steps.push({ kind: "derived", column: d.name, expression: d.expression })
      }
    }
  }

  // Passos derivados das operações (complementam o delta)
  for (const op of ops) {
    if (op.op === "cast_column") {
      steps.push({ kind: "cast", column: op.column, castType: op.data_type })
    } else if (op.op === "filter_rows") {
      steps.push({ kind: "filter", expression: op.expression })
    }
  }

  return steps
}

const builtSteps = computed(() =>
  buildSteps(props.preview?.schemaDelta, props.operations),
)
</script>
