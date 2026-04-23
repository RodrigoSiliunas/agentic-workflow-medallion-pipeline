/**
 * API client wrapper para /api/v1/chat endpoints + SSE stream consumer.
 * Single decision point para mock vs real — stores nunca fazem branching.
 */
import type { ChatMessage, Thread } from "~/types/chat"
import { MOCK_THREADS, mockReplyFor } from "~/composables/mock/threads"
import type { ThreadWithMessages } from "~/composables/mock/threads"

interface ThreadDTO {
  id: string
  pipeline_id: string
  title: string | null
  is_active: boolean
  created_at: string
  updated_at: string
}

interface MessageDTO {
  id: string
  role: string
  content: string
  actions: unknown[] | null
  channel: string | null
  model: string | null
  created_at: string
}

function threadFromApi(dto: ThreadDTO, messageCount = 0): Thread {
  return {
    id: dto.id,
    pipelineId: dto.pipeline_id,
    title: dto.title ?? "Nova conversa",
    lastActivity: dto.updated_at,
    messageCount,
    channel: "web",
  }
}

function messageFromApi(dto: MessageDTO): ChatMessage {
  return {
    id: dto.id,
    role: dto.role as ChatMessage["role"],
    content: dto.content,
    actions: (dto.actions as ChatMessage["actions"]) ?? [],
    channel: (dto.channel as ChatMessage["channel"]) ?? "web",
    timestamp: dto.created_at,
  }
}

export interface ChatStreamHandlers {
  onToken?: (content: string) => void
  onAction?: (action: Record<string, unknown>) => void
  onDone?: () => void
  onError?: (message: string) => void
}

export function useChatApi() {
  const api = useApiClient()
  const auth = useAuthStore()
  const isMock = Boolean(useRuntimeConfig().public.mockMode)

  // Cache local do mock data para mutacoes
  let _mockThreads: ThreadWithMessages[] | null = null
  function getMockThreads(): ThreadWithMessages[] {
    if (!_mockThreads) _mockThreads = structuredClone(MOCK_THREADS)
    return _mockThreads
  }

  async function listThreads(pipelineId?: string): Promise<Thread[]> {
    if (isMock) {
      const all = getMockThreads()
      const filtered = pipelineId ? all.filter((t) => t.pipelineId === pipelineId) : all
      return filtered.map(({ messages: _m, ...thread }) => thread)
    }
    const params: Record<string, string> = {}
    if (pipelineId) params.pipeline_id = pipelineId
    const data = await api.get<ThreadDTO[]>("/chat/threads", params)
    return data.map((t) => threadFromApi(t))
  }

  async function createThread(pipelineId: string): Promise<Thread> {
    if (isMock) {
      const id = `t-${crypto.randomUUID().slice(0, 8)}`
      const thread: ThreadWithMessages = {
        id,
        pipelineId,
        title: "Nova conversa",
        lastActivity: new Date().toISOString(),
        messageCount: 0,
        channel: "web",
        messages: [],
      }
      getMockThreads().unshift(thread)
      return { id: thread.id, pipelineId: thread.pipelineId, title: thread.title, lastActivity: thread.lastActivity, messageCount: 0, channel: "web" }
    }
    const data = await api.post<ThreadDTO>("/chat/threads", {
      pipeline_id: pipelineId,
    })
    return threadFromApi(data)
  }

  async function deleteThread(threadId: string): Promise<void> {
    if (isMock) {
      const threads = getMockThreads()
      const idx = threads.findIndex((t) => t.id === threadId)
      if (idx >= 0) threads.splice(idx, 1)
      return
    }
    await api.delete(`/chat/threads/${threadId}`)
  }

  async function getMessages(threadId: string): Promise<ChatMessage[]> {
    if (isMock) {
      const thread = getMockThreads().find((t) => t.id === threadId)
      return thread ? structuredClone(thread.messages) : []
    }
    const data = await api.get<MessageDTO[]>(`/chat/threads/${threadId}/messages`)
    return data.map(messageFromApi)
  }

  function sendMessageStream(
    threadId: string,
    message: string,
    handlers: ChatStreamHandlers & { model?: string; provider?: string },
  ): () => void {
    if (!import.meta.client) return () => {}

    if (isMock) {
      let cancelled = false
      void (async () => {
        const reply = mockReplyFor(message)
        const tokens = reply.split(" ")
        for (const token of tokens) {
          if (cancelled) break
          await new Promise((r) => setTimeout(r, 35))
          handlers.onToken?.((tokens.indexOf(token) > 0 ? " " : "") + token)
        }
        if (!cancelled) handlers.onDone?.()
      })()
      return () => { cancelled = true }
    }

    const controller = new AbortController()
    const url = `${api.baseURL}/chat/message`

    void (async () => {
      try {
        // Garante token fresco antes do SSE (auto-refresh se expirado)
        if (!auth.accessToken) {
          await auth.refresh()
        }

        let response = await fetch(url, {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            Authorization: `Bearer ${auth.accessToken}`,
            Accept: "text/event-stream",
          },
          body: JSON.stringify({
            thread_id: threadId,
            message,
            model: handlers.model,
            provider: handlers.provider,
          }),
          signal: controller.signal,
          credentials: "include",
        })

        // Token expirado — refresh e retry uma vez
        if (response.status === 401) {
          await auth.refresh()
          if (!auth.accessToken) {
            handlers.onError?.("Sessao expirada. Faca login novamente.")
            return
          }
          response = await fetch(url, {
            method: "POST",
            headers: {
              "Content-Type": "application/json",
              Authorization: `Bearer ${auth.accessToken}`,
              Accept: "text/event-stream",
            },
            body: JSON.stringify({
            thread_id: threadId,
            message,
            model: handlers.model,
            provider: handlers.provider,
          }),
            signal: controller.signal,
            credentials: "include",
          })
        }

        if (!response.ok || !response.body) {
          const errorText = await response.text().catch(() => "")
          console.error("[chat] SSE failed:", response.status, errorText)
          handlers.onError?.(`HTTP ${response.status}: ${errorText}`)
          return
        }

        const reader = response.body.getReader()
        const decoder = new TextDecoder()
        let buffer = ""

        while (true) {
          const { done, value } = await reader.read()
          if (done) break
          buffer += decoder.decode(value, { stream: true })
          const lines = buffer.split("\n")
          buffer = lines.pop() ?? ""
          for (const line of lines) {
            if (!line.startsWith("data: ")) continue
            try {
              const event = JSON.parse(line.slice(6)) as {
                type: string
                content?: string
                [k: string]: unknown
              }
              if (event.type === "token" && typeof event.content === "string") {
                handlers.onToken?.(event.content)
              } else if (event.type === "action") {
                handlers.onAction?.(event)
              } else if (event.type === "done") {
                handlers.onDone?.()
              } else if (event.type === "error") {
                handlers.onError?.(String(event.content ?? "stream error"))
              }
            } catch {
              // malformed
            }
          }
        }
        handlers.onDone?.()
      } catch (e) {
        if (!controller.signal.aborted) {
          console.error("[chat] SSE exception:", e)
          handlers.onError?.(e instanceof Error ? e.message : "chat stream failed")
        }
      }
    })()

    return () => controller.abort()
  }

  return { listThreads, createThread, deleteThread, getMessages, sendMessageStream }
}
