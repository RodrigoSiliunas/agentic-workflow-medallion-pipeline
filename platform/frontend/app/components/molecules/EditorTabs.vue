<template>
  <div
    class="inline-flex gap-0.5 rounded-[var(--radius-md)] border border-[var(--border)] bg-[var(--surface-elevated)] p-[3px]"
    :class="size === 'sm' ? 'h-[36px]' : 'h-[42px]'"
    role="tablist"
  >
    <button
      v-for="tab in tabs"
      :key="tab.id"
      type="button"
      role="tab"
      :aria-selected="tab.id === modelValue"
      :aria-controls="`tabpanel-${tab.id}`"
      class="inline-flex items-center gap-[5px] rounded-[var(--radius-sm)] border border-transparent px-[11px] font-medium transition-all duration-100 focus-visible:outline-none focus-visible:shadow-[var(--shadow-focus)]"
      :class="[
        size === 'sm' ? 'h-[28px] text-[12px]' : 'h-[34px] text-[13px]',
        tab.id === modelValue
          ? 'bg-[var(--surface)] text-[var(--fg-primary)] shadow-[var(--shadow-subtle)]'
          : 'bg-transparent text-[var(--fg-tertiary)] hover:text-[var(--fg-secondary)]',
      ]"
      @click="emit('update:modelValue', tab.id)"
    >
      <AppIcon
        v-if="tab.icon"
        :name="tab.icon"
        size="xs"
        :style="{ color: tab.id === modelValue ? 'var(--brand-500)' : 'var(--fg-tertiary)' }"
      />
      <span>{{ tab.label }}</span>
      <!-- Badge de contagem -->
      <span
        v-if="tab.count != null"
        class="rounded-full px-[5px] font-mono text-[10px] leading-4"
        :style="
          tab.id === modelValue
            ? {
                background: 'var(--surface-elevated)',
                color: 'var(--fg-secondary)',
                border: '1px solid var(--border)',
              }
            : { color: 'var(--fg-tertiary)' }
        "
      >
        {{ tab.count }}
      </span>
    </button>
  </div>
</template>

<script setup lang="ts">
export interface EditorTab {
  id: string
  label: string
  icon?: string
  count?: number | null
}

withDefaults(
  defineProps<{
    tabs: EditorTab[]
    modelValue: string
    size?: "sm" | "md"
  }>(),
  { size: "sm" },
)

const emit = defineEmits<{
  "update:modelValue": [id: string]
}>()
</script>
