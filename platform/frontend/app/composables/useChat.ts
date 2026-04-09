/**
 * Composable para chat — SSE streaming + envio de mensagens.
 */
import type { ChatMessage } from "~/types/chat"

export function useChat(threadId: Ref<string>) {
  const config = useRuntimeConfig()
  const auth = useAuthStore()
  const messages = ref<ChatMessage[]>([])
  const isStreaming = ref(false)
  const loading = ref(false)

  async function loadHistory() {
    loading.value = true
    try {
      const api = useApiClient()
      messages.value = await api.get<ChatMessage[]>(
        `/chat/threads/${threadId.value}/messages`,
      )
    } catch {
      messages.value = []
    } finally {
      loading.value = false
    }
  }

  async function sendMessage(content: string) {
    // Adicionar mensagem do usuario localmente
    const userMsg: ChatMessage = {
      id: crypto.randomUUID(),
      role: "user",
      content,
      channel: "web",
      timestamp: new Date().toISOString(),
    }
    messages.value.push(userMsg)

    // Criar mensagem do assistente (vai preencher via streaming)
    const assistantMsg = reactive<ChatMessage>({
      id: crypto.randomUUID(),
      role: "assistant",
      content: "",
      actions: [],
      channel: "web",
      timestamp: new Date().toISOString(),
    })
    messages.value.push(assistantMsg)

    isStreaming.value = true

    try {
      const response = await fetch(
        `${config.public.apiBase}/chat/message`,
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            Authorization: `Bearer ${auth.accessToken}`,
          },
          body: JSON.stringify({
            thread_id: threadId.value,
            message: content,
          }),
        },
      )

      if (!response.ok) {
        assistantMsg.content = "Erro ao conectar com o agente."
        return
      }

      const reader = response.body!.getReader()
      const decoder = new TextDecoder()
      let buffer = ""

      while (true) {
        const { done, value } = await reader.read()
        if (done) break

        buffer += decoder.decode(value, { stream: true })

        // Processar linhas SSE completas
        const lines = buffer.split("\n")
        buffer = lines.pop() || ""

        for (const line of lines) {
          if (!line.startsWith("data: ")) continue
          try {
            const event = JSON.parse(line.slice(6))

            if (event.type === "token") {
              assistantMsg.content += event.content
            } else if (event.type === "action") {
              assistantMsg.actions = [...(assistantMsg.actions || []), event]
            } else if (event.type === "error") {
              assistantMsg.content += `\n\n⚠️ ${event.content}`
            }
          } catch {
            // Ignorar linhas malformadas
          }
        }
      }
    } catch (e: any) {
      assistantMsg.content = `Erro: ${e.message}`
    } finally {
      isStreaming.value = false
    }
  }

  // Carregar historico quando threadId muda
  watch(threadId, loadHistory, { immediate: true })

  return { messages, isStreaming, loading, sendMessage, loadHistory }
}
