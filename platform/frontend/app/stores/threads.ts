/**
 * Threads store — Pinia store estilo claude.ai para chat.
 * Mock branching foi movido para useChatApi (Strategy pattern).
 */
import { defineStore } from "pinia"
import type { ChatMessage, Thread } from "~/types/chat"

interface ThreadWithMessages extends Thread {
  messages: ChatMessage[]
}

const DEFAULT_PIPELINE_ID = "medallion_pipeline_whatsapp"

function nowISO() {
  return new Date().toISOString()
}

export const useThreadsStore = defineStore("threads", () => {
  const threads = ref<ThreadWithMessages[]>([])
  const activeThreadId = ref<string | null>(null)
  const loadedPipelines = ref<Set<string>>(new Set())
  const loading = ref(false)

  const activeThread = computed(() =>
    threads.value.find((t) => t.id === activeThreadId.value) || null,
  )

  async function loadForPipeline(pipelineId: string, force = false) {
    if (loadedPipelines.value.has(pipelineId) && !force) return
    loading.value = true
    try {
      const api = useChatApi()
      const remote = await api.listThreads(pipelineId)
      // mantém threads de outros pipelines + substitui só as deste
      threads.value = [
        ...threads.value.filter((t) => t.pipelineId !== pipelineId),
        ...remote.map((t) => ({ ...t, messages: [] as ChatMessage[] })),
      ]
      loadedPipelines.value.add(pipelineId)
    } catch (e) {
      console.error("Failed to load threads", e)
    } finally {
      loading.value = false
    }
  }

  async function loadMessages(threadId: string) {
    const thread = getById(threadId)
    if (!thread) return
    try {
      const api = useChatApi()
      thread.messages = await api.getMessages(threadId)
      thread.messageCount = thread.messages.length
    } catch (e) {
      console.error("Failed to load messages", e)
    }
  }

  function getById(id: string): ThreadWithMessages | undefined {
    return threads.value.find((t) => t.id === id)
  }

  function listByPipeline(pipelineId: string): ThreadWithMessages[] {
    return threads.value
      .filter((t) => t.pipelineId === pipelineId)
      .sort(
        (a, b) => new Date(b.lastActivity).getTime() - new Date(a.lastActivity).getTime(),
      )
  }

  /**
   * Agrupa threads em buckets temporais estilo claude.ai:
   * Today / Yesterday / Last 7 days / Last 30 days / Older
   */
  function groupedByBucket(pipelineId?: string): Record<string, ThreadWithMessages[]> {
    const list = pipelineId ? listByPipeline(pipelineId) : [...threads.value]
    const now = new Date()
    const startOfToday = new Date(now.getFullYear(), now.getMonth(), now.getDate())
    const startOfYesterday = new Date(startOfToday)
    startOfYesterday.setDate(startOfYesterday.getDate() - 1)
    const sevenDaysAgo = new Date(startOfToday)
    sevenDaysAgo.setDate(sevenDaysAgo.getDate() - 7)
    const thirtyDaysAgo = new Date(startOfToday)
    thirtyDaysAgo.setDate(thirtyDaysAgo.getDate() - 30)

    const today: ThreadWithMessages[] = []
    const yesterday: ThreadWithMessages[] = []
    const lastSeven: ThreadWithMessages[] = []
    const lastThirty: ThreadWithMessages[] = []
    const older: ThreadWithMessages[] = []

    for (const t of list) {
      const ts = new Date(t.lastActivity)
      if (ts >= startOfToday) today.push(t)
      else if (ts >= startOfYesterday) yesterday.push(t)
      else if (ts >= sevenDaysAgo) lastSeven.push(t)
      else if (ts >= thirtyDaysAgo) lastThirty.push(t)
      else older.push(t)
    }

    const buckets: Record<string, ThreadWithMessages[]> = {
      Today: today,
      Yesterday: yesterday,
      "Last 7 days": lastSeven,
      "Last 30 days": lastThirty,
      Older: older,
    }

    // Remove buckets vazios para exibir mais limpo
    return Object.fromEntries(Object.entries(buckets).filter(([, v]) => v.length > 0))
  }

  async function create(
    title = "Nova conversa",
    pipelineId = DEFAULT_PIPELINE_ID,
  ): Promise<ThreadWithMessages> {
    const api = useChatApi()
    const remote = await api.createThread(pipelineId)
    const full: ThreadWithMessages = {
      ...remote,
      title: title || remote.title,
      messages: [],
    }
    threads.value.unshift(full)
    activeThreadId.value = full.id
    return full
  }

  function setActive(id: string | null) {
    activeThreadId.value = id
  }

  function addMessage(threadId: string, message: Omit<ChatMessage, "id" | "timestamp">) {
    const thread = getById(threadId)
    if (!thread) return null
    const fullMessage: ChatMessage = {
      ...message,
      id: `m-${crypto.randomUUID().slice(0, 8)}`,
      timestamp: nowISO(),
    }
    thread.messages.push(fullMessage)
    thread.messageCount = thread.messages.length
    thread.lastActivity = fullMessage.timestamp
    if (thread.title === "Nova conversa" && message.role === "user") {
      thread.title = message.content.slice(0, 50)
    }
    // Retorna o elemento do array REATIVO (proxy Vue), nao o plain object.
    // Sem isso, `assistantMsg.content += token` no streamAssistantReply
    // muta o objeto original mas Vue nao detecta (bypassa proxy).
    return thread.messages[thread.messages.length - 1]!
  }

  /**
   * Streaming de resposta do LLM. O composable useChatApi ja lida
   * com mock vs real internamente via sendMessageStream.
   */
  async function streamAssistantReply(threadId: string, userContent: string, model?: string): Promise<void> {
    addMessage(threadId, { role: "user", content: userContent, channel: "web" })
    const assistantMsg = addMessage(threadId, {
      role: "assistant",
      content: "",
      channel: "web",
    })
    if (!assistantMsg) return

    const api = useChatApi()
    await new Promise<void>((resolve) => {
      let settled = false
      const finish = () => {
        if (settled) return
        settled = true
        resolve()
      }
      api.sendMessageStream(threadId, userContent, {
        model,
        onToken: (content) => {
          assistantMsg.content += content
        },
        onAction: (action) => {
          assistantMsg.actions = [...(assistantMsg.actions ?? []), action as never]
        },
        onDone: finish,
        onError: (msg) => {
          if (!assistantMsg.content) assistantMsg.content = `Erro: ${msg}`
          finish()
        },
      })
    })
  }

  async function remove(id: string) {
    try {
      const api = useChatApi()
      await api.deleteThread(id)
    } catch (e) {
      console.error("Failed to delete thread", e)
    }
    const idx = threads.value.findIndex((t) => t.id === id)
    if (idx >= 0) threads.value.splice(idx, 1)
    if (activeThreadId.value === id) activeThreadId.value = null
  }

  return {
    threads,
    activeThreadId,
    activeThread,
    loading,
    loadForPipeline,
    loadMessages,
    getById,
    listByPipeline,
    groupedByBucket,
    create,
    setActive,
    addMessage,
    streamAssistantReply,
    remove,
  }
})
