<template>
  <div class="relative w-full">
    <!-- Trigger button -->
    <button
      ref="btnRef"
      type="button"
      class="flex h-[30px] w-full cursor-pointer items-center gap-1.5 rounded-[var(--radius-md)] border border-[var(--border)] bg-[var(--surface-elevated)] px-[10px] text-left font-mono text-[12px] transition-colors duration-100 focus-visible:outline-none focus-visible:shadow-[var(--shadow-focus)]"
      :style="{ color: modelValue ? 'var(--fg-primary)' : 'var(--fg-tertiary)' }"
      @click="toggleOpen"
    >
      <AppIcon name="hashtag" size="xs" :style="{ color: 'var(--fg-tertiary)', flexShrink: 0 }" />
      <span class="flex-1 truncate">{{ selectedColumn?.name || modelValue || placeholder }}</span>
      <AppPill v-if="selectedColumn?.pii" tone="warning" size="xs">PII</AppPill>
      <span
        v-if="selectedColumn"
        class="flex-shrink-0 font-mono text-[10px]"
        :style="{ color: 'var(--fg-tertiary)' }"
      >
        {{ selectedColumn.type }}
      </span>
      <AppPill v-if="isCustom" tone="brand" size="xs">novo</AppPill>
      <AppIcon name="chevron-down" size="xs" :style="{ color: 'var(--fg-tertiary)', flexShrink: 0 }" />
    </button>

    <!-- Dropdown portal -->
    <Teleport to="body">
      <div
        v-if="open"
        ref="menuRef"
        class="fixed z-[220] flex flex-col overflow-hidden rounded-[var(--radius-lg)] border border-[var(--border)] bg-[var(--surface)] shadow-[var(--shadow-medium)]"
        :style="{ top: `${pos.top}px`, left: `${pos.left}px`, width: `${pos.width}px` }"
      >
        <!-- Search input -->
        <div class="border-b border-[var(--border)] p-1.5">
          <div
            class="flex h-[30px] items-center gap-2 rounded-[var(--radius-md)] border border-[var(--border)] bg-[var(--surface-elevated)] px-[10px]"
          >
            <AppIcon name="magnifying-glass" size="sm" :style="{ color: 'var(--fg-tertiary)' }" />
            <input
              ref="inputRef"
              v-model="query"
              placeholder="Filtrar colunas…"
              class="flex-1 border-none bg-transparent font-sans text-[12px] outline-none"
              :style="{ color: 'var(--fg-primary)' }"
              @keydown.enter="pickFirst"
              @keydown.escape="open = false"
            >
          </div>
        </div>

        <!-- Options list -->
        <div class="max-h-[280px] overflow-y-auto p-1">
          <button
            v-for="col in filteredColumns"
            :key="col.name"
            type="button"
            class="flex w-full cursor-pointer items-center gap-2 rounded-[var(--radius-sm)] border-none px-2 py-[7px] text-left transition-colors duration-100 hover:bg-[var(--surface-elevated)]"
            :class="col.name === modelValue ? 'bg-[var(--surface-elevated)]' : 'bg-transparent'"
            @click="pick(col.name)"
          >
            <AppIcon name="hashtag" size="xs" :style="{ color: 'var(--brand-400)' }" />
            <span class="flex min-w-0 flex-1 flex-col gap-[2px]">
              <span class="flex items-center gap-1.5">
                <AppCode class="text-[11px]">{{ col.name }}</AppCode>
                <AppPill v-if="col.pii" tone="warning" size="xs">PII</AppPill>
                <span
                  v-if="col.nullable === false"
                  class="font-mono text-[9px]"
                  :style="{ color: 'var(--fg-tertiary)' }"
                >
                  NOT NULL
                </span>
              </span>
              <span
                v-if="col.comment"
                class="text-[10px]"
                :style="{ color: 'var(--fg-tertiary)' }"
              >
                {{ col.comment }}
              </span>
            </span>
            <span class="flex-shrink-0 font-mono text-[10px]" :style="{ color: 'var(--fg-tertiary)' }">
              {{ col.type }}
            </span>
            <AppIcon
              v-if="col.name === modelValue"
              name="check"
              size="xs"
              :style="{ color: 'var(--brand-400)' }"
            />
          </button>

          <!-- Sem resultados / criar novo -->
          <div
            v-if="filteredColumns.length === 0"
            class="p-3 text-center font-sans text-[12px]"
            :style="{ color: 'var(--fg-tertiary)' }"
          >
            <button
              v-if="allowCreate && query.trim()"
              type="button"
              class="inline-flex cursor-pointer items-center gap-1.5 rounded-[var(--radius-md)] border px-[10px] py-1.5 font-sans text-[11px] font-medium"
              :style="{
                border: '1px solid rgba(142,81,246,0.4)',
                background: 'rgba(142,81,246,0.08)',
                color: 'var(--brand-400)',
              }"
              @click="pick(query.trim())"
            >
              <AppIcon name="plus" size="xs" />
              Criar nova coluna:
              <AppCode class="text-[10px]">{{ query.trim() }}</AppCode>
            </button>
            <span v-else>Nenhuma coluna encontrada</span>
          </div>
        </div>
      </div>
    </Teleport>
  </div>
</template>

<script setup lang="ts">
import type { SchemaColumn } from "~/types/pipeline-editor-v2"

const props = withDefaults(
  defineProps<{
    modelValue?: string
    columns?: SchemaColumn[]
    placeholder?: string
    allowCreate?: boolean
  }>(),
  {
    modelValue: undefined,
    columns: () => [],
    placeholder: "Selecione coluna…",
    allowCreate: false,
  },
)

const emit = defineEmits<{
  "update:modelValue": [value: string]
}>()

const open = ref(false)
const query = ref("")
const pos = ref({ top: 0, left: 0, width: 260 })
const btnRef = ref<HTMLElement | null>(null)
const menuRef = ref<HTMLElement | null>(null)
const inputRef = ref<HTMLInputElement | null>(null)

onClickOutside(menuRef, () => {
  if (open.value) open.value = false
}, { ignore: [btnRef] })

const selectedColumn = computed(() => props.columns.find((c) => c.name === props.modelValue))
const isCustom = computed(() => !!props.modelValue && !selectedColumn.value)

const filteredColumns = computed(() => {
  if (!query.value) return props.columns
  const q = query.value.toLowerCase()
  return props.columns.filter((c) => c.name.toLowerCase().includes(q))
})

function updatePosition() {
  const r = btnRef.value?.getBoundingClientRect()
  if (!r) return
  pos.value = { top: r.bottom + 6, left: r.left, width: Math.max(r.width, 260) }
}

async function toggleOpen() {
  open.value = !open.value
  if (open.value) {
    await nextTick()
    updatePosition()
    inputRef.value?.focus()
  } else {
    query.value = ""
  }
}

function pick(name: string) {
  emit("update:modelValue", name)
  open.value = false
  query.value = ""
}

function pickFirst() {
  if (filteredColumns.value[0]) {
    pick(filteredColumns.value[0].name)
  } else if (props.allowCreate && query.value.trim()) {
    pick(query.value.trim())
  }
}

defineExpose({ open, pick })
</script>
