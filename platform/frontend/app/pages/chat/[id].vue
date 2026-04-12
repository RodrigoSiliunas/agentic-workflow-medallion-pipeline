<template>
  <ChatWindow v-if="thread" :thread-id="thread.id" />
  <EmptyState
    v-else
    icon="face-frown"
    title="Conversa não encontrada"
    description="Essa thread foi removida ou nunca existiu. Comece uma nova conversa."
    class="flex-1"
  />
</template>

<script setup lang="ts">
definePageMeta({ layout: "default" })

const route = useRoute()
const threadsStore = useThreadsStore()
const pipelinesStore = usePipelinesStore()

const threadId = computed(() => String(route.params.id ?? ""))
const thread = computed(() => threadsStore.getById(threadId.value) ?? null)

// Garante que threads do pipeline ativo estao carregadas antes de procurar
await pipelinesStore.load()
const activePipelineId = pipelinesStore.activePipeline?.id
if (activePipelineId) {
  await threadsStore.loadForPipeline(activePipelineId)
}

// Carrega mensagens do thread atual se ainda nao estiverem
if (thread.value && thread.value.messages.length === 0) {
  await threadsStore.loadMessages(thread.value.id)
}

watchEffect(() => {
  if (thread.value) threadsStore.setActive(thread.value.id)
})

onMounted(async () => {
  const seed = route.query.seed
  if (typeof seed === "string" && thread.value && thread.value.messages.length === 0) {
    await threadsStore.streamAssistantReply(thread.value.id, seed)
    navigateTo({ path: route.path }, { replace: true })
  }
})
</script>
