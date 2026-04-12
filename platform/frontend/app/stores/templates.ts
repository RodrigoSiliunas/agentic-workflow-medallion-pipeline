/**
 * Templates store — marketplace de pipeline templates one-click deploy.
 * Mock branching foi movido para useTemplatesApi (Strategy pattern).
 */
import { defineStore } from "pinia"
import type { Template } from "~/types/template"

export const useTemplatesStore = defineStore("templates", () => {
  const templates = ref<Template[]>([])
  const searchQuery = ref("")
  const activeCategory = ref<string | null>(null)
  const loaded = ref(false)
  const loading = ref(false)

  async function load(force = false) {
    if (loaded.value && !force) return
    loading.value = true
    try {
      const api = useTemplatesApi()
      templates.value = await api.list()
      loaded.value = true
    } catch (e) {
      console.error("Failed to load templates", e)
      templates.value = []
      loaded.value = true
    } finally {
      loading.value = false
    }
  }

  const categories = computed(() => {
    const set = new Set<string>()
    for (const t of templates.value) set.add(t.category)
    return Array.from(set)
  })

  const filtered = computed(() => {
    const q = searchQuery.value.trim().toLowerCase()
    return templates.value.filter((t) => {
      if (activeCategory.value && t.category !== activeCategory.value) return false
      if (!q) return true
      const haystack = [t.name, t.tagline, t.description, ...t.tags].join(" ").toLowerCase()
      return haystack.includes(q)
    })
  })

  function getBySlug(slug: string): Template | undefined {
    return templates.value.find((t) => t.slug === slug)
  }

  function setSearch(q: string) {
    searchQuery.value = q
  }

  function setCategory(c: string | null) {
    activeCategory.value = c
  }

  return {
    templates,
    searchQuery,
    activeCategory,
    categories,
    filtered,
    loaded,
    loading,
    load,
    getBySlug,
    setSearch,
    setCategory,
  }
})
