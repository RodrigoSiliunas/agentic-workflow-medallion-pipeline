<template>
  <div class="flex flex-col h-full overflow-hidden">
    <!-- Toolbar -->
    <div class="px-6 pt-6 pb-4">
      <div class="flex items-center gap-3 flex-wrap">
        <AppInput
          v-model="localSearch"
          placeholder="Buscar templates..."
          icon="i-heroicons-magnifying-glass"
          size="md"
          class="max-w-sm"
          @update:model-value="onSearch"
        />
        <div class="flex items-center gap-1">
          <button
            class="px-3 py-1.5 rounded-[var(--radius-md)] text-[11px] font-medium transition-colors border"
            :style="chipStyle(null)"
            @click="setCategory(null)"
          >
            Todos
          </button>
          <button
            v-for="cat in templatesStore.categories"
            :key="cat"
            class="px-3 py-1.5 rounded-[var(--radius-md)] text-[11px] font-medium transition-colors border"
            :style="chipStyle(cat)"
            @click="setCategory(cat)"
          >
            {{ cat }}
          </button>
        </div>
      </div>
    </div>

    <!-- Grid -->
    <div class="flex-1 overflow-y-auto px-6 pb-8">
      <div
        v-if="templatesStore.filtered.length > 0"
        class="grid gap-4 grid-cols-1 md:grid-cols-2 xl:grid-cols-3"
      >
        <TemplateCard
          v-for="template in templatesStore.filtered"
          :key="template.slug"
          :template="template"
        />
      </div>
      <EmptyState
        v-else
        icon="magnifying-glass"
        title="Nenhum template encontrado"
        description="Ajuste a busca ou limpe os filtros para ver todos os templates disponiveis."
      />
    </div>
  </div>
</template>

<script setup lang="ts">
const templatesStore = useTemplatesStore()
const localSearch = ref(templatesStore.searchQuery)

function onSearch(value: string) {
  templatesStore.setSearch(value)
}

function setCategory(cat: string | null) {
  templatesStore.setCategory(cat)
}

function chipStyle(cat: string | null): Record<string, string> {
  const isActive = templatesStore.activeCategory === cat
  return {
    background: isActive ? "var(--brand-600)" : "var(--surface)",
    color: isActive ? "white" : "var(--text-secondary)",
    borderColor: isActive ? "var(--brand-600)" : "var(--border)",
  }
}
</script>
