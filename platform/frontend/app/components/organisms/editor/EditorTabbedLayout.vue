<script setup lang="ts">
// ---------------------------------------------------------------------------
// Props & emits
// ---------------------------------------------------------------------------
const props = withDefaults(defineProps<{
  tabs?: string[]
  modelValue: string
}>(), {
  tabs: () => ["Chat", "Rascunho", "Preview", "PR"],
})

const emit = defineEmits<{
  "update:modelValue": [value: string]
}>()

// Converte array de strings para o formato esperado por EditorTabs
const tabItems = computed(() =>
  props.tabs.map((label) => ({ id: label.toLowerCase().replace(/\s+/g, "-"), label }))
)
</script>

<template>
  <!-- Layout em abas: uma coluna, conteúdo trocado por aba ativa -->
  <div class="tabbed-layout">
    <!-- Aba de navegação no topo -->
    <EditorTabs
      :tabs="tabItems"
      :model-value="modelValue"
      size="md"
      @update:model-value="emit('update:modelValue', $event)"
    />

    <!-- Painel de conteúdo da aba ativa -->
    <div class="tab-content">
      <slot />
    </div>
  </div>
</template>

<style scoped>
/* Layout raiz tabulado */
.tabbed-layout {
  display: flex;
  flex-direction: column;
  height: 100%;
}

/* Painel de conteúdo — ocupa todo o espaço restante */
.tab-content {
  flex: 1;
  min-height: 0;
  overflow: hidden;
}
</style>
