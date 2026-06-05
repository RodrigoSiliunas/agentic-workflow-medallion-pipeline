import type { ModelProvider } from "~/types/pipeline-editor-v2"

export const OP_TYPES = [
  { id: "rename_column",  label: "Renomear coluna",   icon: "arrows-right-left" },
  { id: "drop_column",    label: "Remover coluna",    icon: "minus-circle" },
  { id: "cast_column",    label: "Cast de tipo",      icon: "arrow-path" },
  { id: "trim",           label: "Trim",              icon: "scissors" },
  { id: "regex_replace",  label: "Regex replace",     icon: "magnifying-glass" },
  { id: "coalesce",       label: "Coalesce",          icon: "rectangle-stack" },
  { id: "derive_column",  label: "Coluna derivada",   icon: "plus-circle" },
  { id: "filter_rows",    label: "Filtrar linhas",    icon: "funnel" },
  { id: "date_format",    label: "Formatar data",     icon: "calendar" },
  { id: "json_extract",   label: "JSON extract",      icon: "code-bracket" },
  { id: "mask_pii",       label: "Mascarar PII",      icon: "eye-slash" },
] as const

export const OP_ICON: Record<string, { icon: string; color: string }> = {
  drop_column:    { icon: "minus-circle",       color: "var(--status-error)" },
  rename_column:  { icon: "arrows-right-left",  color: "var(--status-info)" },
  cast_column:    { icon: "arrow-path",         color: "var(--brand-400)" },
  trim:           { icon: "scissors",           color: "var(--fg-secondary)" },
  regex_replace:  { icon: "magnifying-glass",   color: "var(--brand-400)" },
  coalesce:       { icon: "rectangle-stack",    color: "var(--brand-400)" },
  derive_column:  { icon: "plus-circle",        color: "var(--status-success)" },
  filter_rows:    { icon: "funnel",             color: "var(--status-warning)" },
  date_format:    { icon: "calendar",           color: "var(--brand-400)" },
  json_extract:   { icon: "code-bracket",       color: "var(--brand-400)" },
  mask_pii:       { icon: "eye-slash",          color: "var(--status-warning)" },
}

export const SPARK_DATA_TYPES = [
  "string", "integer", "long", "double", "float", "decimal(18,2)", "decimal(38,10)",
  "boolean", "date", "timestamp", "binary", "array<string>", "map<string,string>",
]

export const MODEL_PROVIDERS: ModelProvider[] = [
  {
    id: "anthropic", name: "Anthropic", iconName: "sparkles",
    models: [
      { id: "claude-opus-4.6",   label: "Claude Opus 4.6",   hint: "Mais capaz · análises complexas" },
      { id: "claude-sonnet-4.6", label: "Claude Sonnet 4.6", hint: "Equilíbrio velocidade/qualidade", default: true },
      { id: "claude-haiku-4.5",  label: "Claude Haiku 4.5",  hint: "Mais rápido · ops simples" },
    ],
  },
  {
    id: "openai", name: "OpenAI", iconName: "cpu-chip",
    models: [
      { id: "gpt-5",      label: "GPT-5",      hint: "Geração mais recente" },
      { id: "gpt-5-mini", label: "GPT-5 mini", hint: "Menor custo" },
    ],
  },
  {
    id: "databricks", name: "Databricks", iconName: "circle-stack",
    models: [
      { id: "dbrx-instruct", label: "DBRX Instruct", hint: "Self-hosted no workspace" },
      { id: "llama-3.3-70b", label: "Llama 3.3 70B", hint: "Foundation Model API" },
    ],
  },
]

export const LAYOUT_OPTIONS = [
  { value: "tri_pane",      label: "Tri-pane (padrão)" },
  { value: "chat_dominant", label: "Chat dominante" },
  { value: "wizard",        label: "Stage/Wizard" },
  { value: "tabbed",        label: "Tabbed (1 coluna)" },
  { value: "conservative",  label: "Conservador (V1+)" },
] as const
