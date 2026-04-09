/**
 * Composable para estado da sidebar.
 */
export function useSidebar() {
  const expandedPipelineId = ref<string | null>(null)
  const activePipelineId = ref<string | null>(null)
  const activeThreadId = ref<string | null>(null)

  function togglePipeline(pipelineId: string) {
    expandedPipelineId.value =
      expandedPipelineId.value === pipelineId ? null : pipelineId
    if (expandedPipelineId.value) {
      activePipelineId.value = pipelineId
    }
  }

  function selectThread(pipelineId: string, threadId: string) {
    activePipelineId.value = pipelineId
    activeThreadId.value = threadId
    navigateTo(`/chat/${pipelineId}/${threadId}`)
  }

  return {
    expandedPipelineId,
    activePipelineId,
    activeThreadId,
    togglePipeline,
    selectThread,
  }
}
