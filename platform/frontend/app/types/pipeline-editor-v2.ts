import type {
  TransformDraft,
  TransformOperation,
  EditProposal,
  PipelineWorkspace,
  PipelineEditSession,
  PipelineEditVersion,
  ApproveEditResponse,
} from "./pipeline-editor"

export type {
  TransformDraft,
  TransformOperation,
  EditProposal,
  PipelineWorkspace,
  PipelineEditSession,
  PipelineEditVersion,
  ApproveEditResponse,
}

// Estado da máquina de estados da sessão de edição
export type StateMachineState =
  | "idle"
  | "generating_proposal"
  | "running_preview"
  | "validating"
  | "opening_pr"
  | "pr_created"
  | "validation_failed"
  | "error"

// Status de uma sessão de edição (exibido nos pills e rail)
export type SessionStatusV2 =
  | "draft"
  | "preview_ok"
  | "pr_created"
  | "validated"
  | "validation_failed"

// Qual lado está dirigindo o rascunho ativo
export type SourceOfTruth = "chat" | "builder" | null

// Aba ativa no inspector direito
export type InspectorTab = "rascunho" | "preview" | "pr"

// Variantes de layout do editor
export type LayoutVariant = "tri_pane" | "wizard" | "tabbed" | "chat_dominant" | "conservative"

// Mensagem no thread do editor (separada de ChatMessage do chat geral)
export interface EditorChatMessage {
  role: "user" | "assistant"
  content: string
  author?: string
  time?: string
  proposal?: EditProposal
  streaming?: boolean
}

// Linha de schema (coluna de uma tabela Delta)
export interface SchemaColumn {
  name: string
  type: string
  nullable?: boolean
  pii?: boolean
  comment?: string
  // Estado após o diff — ausente = sem mudança
  state?: "added" | "removed" | "renamed" | "modified" | "derived" | "unchanged"
  from?: string // nome anterior quando state === "renamed"
  note?: string
}

// Diff de schema entre antes e depois da proposta
export interface SchemaDelta {
  renamed?: Array<{ from: string; to: string }>
  removed?: string[]
  derived?: Array<string | { name: string; expression: string }>
  modified?: string[]
}

// Resultado do preview Databricks (RF-06)
export interface PreviewResultV2 {
  status: "ready" | "running" | "failed"
  schemaBefore?: SchemaColumn[]
  schemaAfter?: SchemaColumn[]
  schemaDelta?: SchemaDelta
  rowsAfter?: Record<string, unknown>[]
  rowsBefore?: Record<string, unknown>[]
  error?: string
}

// Item individual de checklist de validação
export interface ValidationCheck {
  label: string
  state: "ok" | "fail" | "running" | "pending"
}

// Resultado completo da validação pré-PR (RF-07/08)
export interface ValidationResult {
  valid: boolean
  checks: ValidationCheck[]
  error?: string
}

// Linha de um diff de arquivo
export interface DiffLine {
  type: "added" | "removed" | "context"
  content: string
  lineNumber?: number
}

// Diff de um arquivo individual (para EditorFileDiffModal — PR-B)
export interface FileDiff {
  path: string
  additions: number
  deletions: number
  patch: string
  lines?: DiffLine[]
}

// Preferências persistidas do editor (via useEditorSettings — PR-C)
export interface EditorSettings {
  layout: LayoutVariant
  density: "compact" | "comfortable"
  showSessionsRail: boolean
  showStateTimeline: boolean
}

// Modelo de IA individual no picker
export interface ModelOption {
  id: string
  label: string
  hint: string
  default?: boolean
}

// Provedor de IA com lista de modelos (Anthropic/OpenAI/Databricks)
export interface ModelProvider {
  id: string
  name: string
  iconName: string
  models: ModelOption[]
}
