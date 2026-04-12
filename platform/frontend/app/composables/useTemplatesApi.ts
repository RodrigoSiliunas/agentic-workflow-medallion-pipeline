/**
 * API client wrapper for /api/v1/templates endpoints.
 * Single decision point para mock vs real — stores nunca fazem branching.
 */
import type { Template } from "~/types/template"
import { MOCK_TEMPLATES } from "~/composables/mock/templates"

interface TemplateApiDTO {
  id: string
  slug: string
  name: string
  tagline: string
  description: string
  category: string
  tags: string[]
  icon: string
  icon_bg: string
  version: string
  author: string
  deploy_count: number
  duration_estimate: string
  architecture_bullets: string[]
  env_schema: Array<Record<string, unknown>>
  changelog: Array<Record<string, unknown>>
  published: boolean
}

function fromApi(dto: TemplateApiDTO): Template {
  return {
    slug: dto.slug,
    name: dto.name,
    tagline: dto.tagline,
    description: dto.description,
    category: dto.category as Template["category"],
    tags: dto.tags ?? [],
    icon: dto.icon,
    iconBg: dto.icon_bg,
    version: dto.version,
    author: dto.author,
    deployCount: dto.deploy_count,
    durationEstimate: dto.duration_estimate,
    architectureBullets: dto.architecture_bullets ?? [],
    envSchema: (dto.env_schema ?? []).map((s) => ({
      key: String(s.key ?? ""),
      label: String(s.label ?? ""),
      type: (s.type as Template["envSchema"][number]["type"]) ?? "text",
      required: Boolean(s.required),
      placeholder: s.placeholder as string | undefined,
      helper: s.helper as string | undefined,
      default: s.default as string | undefined,
      options: s.options as string[] | undefined,
    })),
    changelog: (dto.changelog ?? []).map((c) => ({
      version: String(c.version ?? ""),
      date: String(c.date ?? ""),
      changes: (c.changes as string[]) ?? [],
    })),
    published: dto.published,
  }
}

export function useTemplatesApi() {
  const api = useApiClient()
  const isMock = Boolean(useRuntimeConfig().public.mockMode)

  async function list(params?: { category?: string; search?: string }): Promise<Template[]> {
    if (isMock) {
      let result = structuredClone(MOCK_TEMPLATES)
      if (params?.category) result = result.filter((t) => t.category === params.category)
      if (params?.search) {
        const q = params.search.toLowerCase()
        result = result.filter((t) =>
          [t.name, t.tagline, t.description, ...t.tags].join(" ").toLowerCase().includes(q),
        )
      }
      return result
    }
    const query: Record<string, string> = {}
    if (params?.category) query.category = params.category
    if (params?.search) query.search = params.search
    const data = await api.get<TemplateApiDTO[]>("/templates", query)
    return data.map(fromApi)
  }

  async function getBySlug(slug: string): Promise<Template | null> {
    if (isMock) {
      return structuredClone(MOCK_TEMPLATES).find((t) => t.slug === slug) ?? null
    }
    try {
      const data = await api.get<TemplateApiDTO>(`/templates/${slug}`)
      return fromApi(data)
    } catch {
      return null
    }
  }

  return { list, getBySlug }
}
