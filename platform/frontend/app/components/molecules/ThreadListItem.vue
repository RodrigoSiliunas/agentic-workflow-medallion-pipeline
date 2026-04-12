<template>
  <div
    class="group w-full flex items-center gap-2 px-3 py-2 rounded-[var(--radius-md)] text-sm text-left transition-colors cursor-pointer select-none"
    :class="[
      isActive
        ? 'bg-[var(--surface-elevated)] text-[var(--text-primary)]'
        : 'text-[var(--text-secondary)] hover:bg-[var(--surface-elevated)]/60 hover:text-[var(--text-primary)]',
    ]"
    role="button"
    :tabindex="0"
    @click="$emit('select', thread.id)"
    @keydown.enter.prevent="$emit('select', thread.id)"
    @keydown.space.prevent="$emit('select', thread.id)"
  >
    <span class="flex-1 truncate">{{ thread.title }}</span>
    <button
      type="button"
      class="opacity-0 group-hover:opacity-100 transition-opacity p-0.5 rounded hover:bg-[var(--border)]"
      :aria-label="`Apagar conversa ${thread.title}`"
      @click.stop="$emit('delete', thread.id)"
      @keydown.enter.stop="$emit('delete', thread.id)"
      @keydown.space.stop="$emit('delete', thread.id)"
    >
      <AppIcon name="trash" size="xs" class="text-[var(--text-tertiary)]" />
    </button>
  </div>
</template>

<script setup lang="ts">
import type { Thread } from "~/types/chat"

defineProps<{
  thread: Thread
  isActive: boolean
}>()

defineEmits<{
  select: [id: string]
  delete: [id: string]
}>()
</script>
