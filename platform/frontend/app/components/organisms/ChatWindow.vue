<template>
  <div class="flex-1 flex flex-col overflow-hidden">
    <WorkflowHeader :pipeline="activePipeline" :thread-title="thread?.title" />

    <MessageList :messages="messages" :is-streaming="isStreaming" />

    <MessageInput :disabled="isStreaming" @send="handleSend" @update:model="selectedModel = $event" />
  </div>
</template>

<script setup lang="ts">
const props = defineProps<{ threadId: string }>()

const threadsStore = useThreadsStore()
const pipelinesStore = usePipelinesStore()

const thread = computed(() => threadsStore.getById(props.threadId) ?? null)
const messages = computed(() => thread.value?.messages ?? [])
const activePipeline = computed(() => {
  const pid = thread.value?.pipelineId
  if (!pid) return pipelinesStore.activePipeline
  return pipelinesStore.getById(pid) ?? null
})

const isStreaming = ref(false)
const selectedModel = ref("sonnet")

async function handleSend(content: string) {
  if (isStreaming.value || !thread.value) return
  isStreaming.value = true
  try {
    await threadsStore.streamAssistantReply(props.threadId, content, selectedModel.value)
  } finally {
    isStreaming.value = false
  }
}

watchEffect(() => {
  if (props.threadId) threadsStore.setActive(props.threadId)
})
</script>
