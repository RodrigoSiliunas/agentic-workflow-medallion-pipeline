<template>
  <div class="flex-1 flex flex-col overflow-hidden">
    <WorkflowHeader
      :pipeline="activePipeline"
      :thread-title="thread?.title"
      :thread-id="props.threadId"
      :model-value-provider="selectedProvider"
      :model-value-model="selectedModel"
      @refresh="refreshMessages"
      @clear="clearThread"
      @change-llm="onChangeLlm"
    />

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
const selectedProvider = ref("")
const selectedModel = ref("")

function onChangeLlm(provider: string, model: string) {
  selectedProvider.value = provider
  selectedModel.value = model
}

async function handleSend(content: string) {
  if (isStreaming.value || !thread.value) return
  isStreaming.value = true
  try {
    await threadsStore.streamAssistantReply(
      props.threadId,
      content,
      selectedModel.value || undefined,
      selectedProvider.value || undefined,
    )
  } finally {
    isStreaming.value = false
  }
}

async function refreshMessages() {
  if (thread.value) {
    await threadsStore.loadMessages(thread.value.id)
  }
}

async function clearThread() {
  if (thread.value) {
    threadsStore.remove(thread.value.id)
    navigateTo("/chat")
  }
}

watchEffect(() => {
  if (props.threadId) threadsStore.setActive(props.threadId)
})
</script>
