export type TemplateCategory = "ETL" | "CRM" | "E-commerce" | "Analytics" | "Observability"

export interface EnvVarSchema {
  key: string
  label: string
  type: "text" | "password" | "url" | "cron" | "select"
  required: boolean
  placeholder?: string
  helper?: string
  default?: string
  options?: string[]
}

export interface TemplateChangelog {
  version: string
  date: string
  changes: string[]
}

export interface Template {
  slug: string
  name: string
  tagline: string
  description: string
  category: TemplateCategory
  tags: string[]
  icon: string
  iconBg: string
  version: string
  author: string
  deployCount: number
  durationEstimate: string
  architectureBullets: string[]
  envSchema: EnvVarSchema[]
  changelog: TemplateChangelog[]
  published: boolean
}
