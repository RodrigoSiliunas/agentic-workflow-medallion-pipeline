// Mock STT — sem microfone/Web Speech API, transcrição determinística após ~2.4s.

const MOCK_TRANSCRIPTS = [
  "Renomeie cliente_id para customer_id em silver.messages",
  "Remova a coluna ssn que é PII desnecessária no Silver",
  "Aplique trim em nome_completo para normalizar os espaços",
  "Mascara o CPF usando HMAC na coluna cpf",
  "Filtre as mensagens com status cancelado",
]

export function useMockDictation(onTranscript: (text: string) => void) {
  const listening = ref(false)
  let transcriptIndex = 0
  let timer: ReturnType<typeof setTimeout> | null = null

  function toggle() {
    if (listening.value) {
      stop()
    } else {
      start()
    }
  }

  function start() {
    if (listening.value) return
    listening.value = true
    // Mock: emite transcrição após ~2.4s
    timer = setTimeout(() => {
      const text = MOCK_TRANSCRIPTS[transcriptIndex % MOCK_TRANSCRIPTS.length]
      transcriptIndex++
      listening.value = false
      timer = null
      onTranscript(text)
    }, 2400)
  }

  function stop() {
    listening.value = false
    if (timer !== null) {
      clearTimeout(timer)
      timer = null
    }
  }

  onUnmounted(stop)

  return { listening, toggle, start, stop }
}
