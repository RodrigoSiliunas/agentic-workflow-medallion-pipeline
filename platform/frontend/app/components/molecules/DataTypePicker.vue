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
      <AppIcon name="cube" size="xs" :style="{ color: 'var(--fg-tertiary)', flexShrink: 0 }" />
      <span class="flex-1 truncate">{{ modelValue || "Selecione tipo…" }}</span>
      <AppIcon name="chevron-down" size="xs" :style="{ color: 'var(--fg-tertiary)', flexShrink: 0 }" />
    </button>

    <!-- Dropdown portal -->
    <Teleport to="body">
      <div
        v-if="open"
        ref="menuRef"
        class="fixed z-[220] overflow-hidden rounded-[var(--radius-lg)] border border-[var(--border)] bg-[var(--surface)] shadow-[var(--shadow-medium)]"
        :style="{ top: `${pos.top}px`, left: `${pos.left}px`, width: `${pos.width}px` }"
      >
        <div class="max-h-[280px] overflow-y-auto p-1">
          <button
            v-for="type in effectiveOptions"
            :key="type"
            type="button"
            class="flex w-full cursor-pointer items-center gap-2 rounded-[var(--radius-sm)] border-none px-[10px] py-[7px] text-left font-mono text-[12px] transition-colors duration-100 hover:bg-[var(--surface-elevated)]"
            :class="type === modelValue ? 'bg-[var(--surface-elevated)]' : 'bg-transparent'"
            :style="{ color: 'var(--fg-primary)' }"
            @click="pick(type)"
          >
            <span class="flex-1">{{ type }}</span>
            <AppIcon
              v-if="type === modelValue"
              name="check"
              size="xs"
              :style="{ color: 'var(--brand-400)' }"
            />
          </button>
        </div>
      </div>
    </Teleport>
  </div>
</template>

<script setup lang="ts">
// Tipos Spark padrão (port fiel do protótipo fbaf2c9a)
const SPARK_DATA_TYPES = [
  "string",
  "int",
  "bigint",
  "double",
  "float",
  "decimal(18,2)",
  "decimal(38,18)",
  "boolean",
  "timestamp",
  "date",
  "binary",
  "array<string>",
  "map<string,string>",
]

const props = defineProps<{
  modelValue?: string
  options?: string[]
}>()

const effectiveOptions = computed(() => props.options ?? SPARK_DATA_TYPES)

const emit = defineEmits<{
  "update:modelValue": [value: string]
}>()

const open = ref(false)
const pos = ref({ top: 0, left: 0, width: 220 })
const btnRef = ref<HTMLElement | null>(null)
const menuRef = ref<HTMLElement | null>(null)

onClickOutside(menuRef, () => {
  if (open.value) open.value = false
}, { ignore: [btnRef] })

function updatePosition() {
  const r = btnRef.value?.getBoundingClientRect()
  if (!r) return
  pos.value = { top: r.bottom + 6, left: r.left, width: Math.max(r.width, 220) }
}

async function toggleOpen() {
  open.value = !open.value
  if (open.value) {
    await nextTick()
    updatePosition()
  }
}

function pick(type: string) {
  emit("update:modelValue", type)
  open.value = false
}
</script>
