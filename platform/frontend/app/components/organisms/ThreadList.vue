<template>
  <div class="flex-1 overflow-y-auto px-2 py-2 space-y-4">
    <div v-for="(items, bucket) in groups" :key="bucket" class="space-y-0.5">
      <h4
        class="px-3 pb-1 text-[10px] uppercase tracking-wider font-medium"
        :style="{ color: 'var(--text-tertiary)' }"
      >
        {{ bucket }}
      </h4>
      <ThreadListItem
        v-for="thread in items"
        :key="thread.id"
        :thread="thread"
        :is-active="thread.id === activeId"
        @select="$emit('select', $event)"
        @delete="$emit('delete', $event)"
      />
    </div>

    <EmptyState
      v-if="isEmpty"
      icon="chat-bubble-left-right"
      title="Sem conversas ainda"
      description="Comece uma nova conversa com o agente do pipeline."
    />
  </div>
</template>

<script setup lang="ts">
import type { Thread } from "~/types/chat"

const props = defineProps<{
  groups: Record<string, Thread[]>
  activeId: string | null
}>()

defineEmits<{
  select: [id: string]
  delete: [id: string]
}>()

const isEmpty = computed(() => Object.values(props.groups).every((g) => g.length === 0))
</script>
