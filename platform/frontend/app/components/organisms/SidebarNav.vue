<template>
  <div class="space-y-1">
    <!-- Search -->
    <div class="px-2 pb-2">
      <UInput
        v-model="search"
        placeholder="Buscar pipeline..."
        icon="i-heroicons-magnifying-glass"
        size="xs"
      />
    </div>

    <!-- Pipeline list -->
    <div v-for="pipeline in filteredPipelines" :key="pipeline.id">
      <!-- Pipeline item -->
      <button
        class="w-full flex items-center gap-2 px-3 py-2 rounded-lg text-sm text-left transition-colors"
        :style="{
          background: sidebar.expandedPipelineId === pipeline.id ? 'var(--bg-elevated)' : 'transparent',
          color: 'var(--text-primary)',
        }"
        @click="handlePipelineClick(pipeline.id)"
      >
        <UIcon
          :name="sidebar.expandedPipelineId === pipeline.id ? 'i-heroicons-chevron-down' : 'i-heroicons-chevron-right'"
          class="text-xs flex-shrink-0"
          style="color: var(--text-tertiary)"
        />
        <span class="flex-1 truncate">{{ pipeline.name }}</span>
        <StatusBadge :status="pipeline.status || 'IDLE'" />
      </button>

      <!-- Threads (expandido) -->
      <div v-if="sidebar.expandedPipelineId === pipeline.id" class="ml-5 mt-1 space-y-0.5">
        <button
          v-for="thread in pipelineThreads"
          :key="thread.id"
          class="w-full flex items-center gap-2 px-3 py-1.5 rounded-md text-xs text-left transition-colors group"
          :style="{
            background: sidebar.activeThreadId === thread.id ? 'var(--bg-elevated)' : 'transparent',
            borderLeft: sidebar.activeThreadId === thread.id ? '2px solid var(--brand-primary)' : '2px solid transparent',
          }"
          @click="sidebar.selectThread(pipeline.id, thread.id)"
        >
          <ChannelIcon v-if="thread.channel && thread.channel !== 'web'" :channel="thread.channel" size="xs" />
          <span class="flex-1 truncate" style="color: var(--text-secondary)">
            {{ thread.title || '(sem titulo)' }}
          </span>
          <UButton
            variant="ghost"
            icon="i-heroicons-x-mark"
            size="xs"
            class="opacity-0 group-hover:opacity-100"
            @click.stop="handleDeleteThread(thread.id)"
          />
        </button>

        <!-- + Nova conversa -->
        <button
          class="w-full flex items-center gap-2 px-3 py-1.5 rounded-md text-xs transition-colors"
          style="color: var(--brand-primary)"
          @click="handleNewThread(pipeline.id)"
        >
          <UIcon name="i-heroicons-plus" class="text-xs" />
          <span>Nova conversa</span>
        </button>
      </div>
    </div>

    <!-- Empty state -->
    <div v-if="filteredPipelines.length === 0" class="px-3 py-4 text-center">
      <p class="text-xs" style="color: var(--text-tertiary)">
        {{ pipelines.length === 0 ? 'Nenhum pipeline' : 'Nenhum resultado' }}
      </p>
    </div>
  </div>
</template>

<script setup lang="ts">
import type { Pipeline } from "~/types/pipeline"
import type { Thread } from "~/types/chat"

const props = defineProps<{
  pipelines: Pipeline[]
}>()

const sidebar = useSidebar()
const search = ref("")

const filteredPipelines = computed(() => {
  if (!search.value) return props.pipelines
  const q = search.value.toLowerCase()
  return props.pipelines.filter((p) => p.name.toLowerCase().includes(q))
})

// Threads do pipeline expandido
const activePipelineId = computed(() => sidebar.expandedPipelineId)
const { threads: pipelineThreads, create, remove } = useThreads(activePipelineId)

function handlePipelineClick(pipelineId: string) {
  sidebar.togglePipeline(pipelineId)
}

async function handleNewThread(pipelineId: string) {
  const thread = await create()
  if (thread) {
    sidebar.selectThread(pipelineId, thread.id)
  }
}

async function handleDeleteThread(threadId: string) {
  await remove(threadId)
}
</script>
