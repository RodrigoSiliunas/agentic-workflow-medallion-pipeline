import type { EditorSettings } from "~/types/pipeline-editor-v2"

const DEFAULTS: EditorSettings = {
  layout: "tri_pane",
  showStateTimeline: true,
  density: "comfortable",
  showSessionsRail: true,
}

export function useEditorSettings() {
  const settings = useLocalStorage<EditorSettings>("flowertex.editor.settings", DEFAULTS)

  function reset() {
    settings.value = { ...DEFAULTS }
  }

  return { settings, reset }
}
