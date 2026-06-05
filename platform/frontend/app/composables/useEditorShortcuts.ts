// NF-03: Atalhos de teclado do Pipeline Editor V2.

interface EditorShortcutHandlers {
  onSend?: () => void
  onEscape?: () => void
  onSaveDraft?: () => void
  onRunPreview?: () => void
  onNewSession?: () => void
  onShare?: () => void
  onHelp?: () => void
}

function isInputFocused(): boolean {
  const tag = (document.activeElement?.tagName || "").toLowerCase()
  return tag === "input" || tag === "textarea" || tag === "select"
}

export function useEditorShortcuts(handlers: EditorShortcutHandlers) {
  function onKeydown(e: KeyboardEvent) {
    const ctrl = e.ctrlKey || e.metaKey

    if (e.key === "Enter" && ctrl) {
      e.preventDefault()
      handlers.onSend?.()
      return
    }
    if (e.key === "Escape") {
      handlers.onEscape?.()
      return
    }
    if (e.key === "s" && ctrl) {
      e.preventDefault()
      handlers.onSaveDraft?.()
      return
    }
    if (e.key === "p" && ctrl) {
      e.preventDefault()
      handlers.onRunPreview?.()
      return
    }
    if (e.key === "n" && ctrl) {
      e.preventDefault()
      handlers.onNewSession?.()
      return
    }
    if (e.key === "k" && ctrl) {
      e.preventDefault()
      handlers.onShare?.()
      return
    }
    // `?` toggle shortcuts — ignorar quando foco está em input/textarea
    if (e.key === "?" && !ctrl && !e.shiftKey) {
      if (!isInputFocused()) {
        e.preventDefault()
        handlers.onHelp?.()
      }
    }
  }

  onMounted(() => window.addEventListener("keydown", onKeydown))
  onUnmounted(() => window.removeEventListener("keydown", onKeydown))
}
