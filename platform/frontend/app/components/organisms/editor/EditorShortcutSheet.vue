<script setup lang="ts">
// Modal de lista de atalhos de teclado do pipeline editor
defineProps<{
  open: boolean
}>()

const emit = defineEmits<{
  close: []
}>()

// Lista de atalhos de teclado disponíveis
const shortcuts: Array<{
  label: string
  keys: string[]
}> = [
  { label: "Enviar mensagem NL", keys: ["Ctrl", "↵"] },
  { label: "Quebrar linha no chat", keys: ["Shift", "↵"] },
  { label: "Salvar rascunho do builder", keys: ["Ctrl", "S"] },
  { label: "Rodar preview", keys: ["Ctrl", "P"] },
  { label: "Abrir modal de aprovação", keys: ["Ctrl", "Enter"] },
  { label: "Fechar modal / cancelar", keys: ["Esc"] },
  { label: "Nova sessão", keys: ["Ctrl", "N"] },
  { label: "Compartilhar sessão", keys: ["Ctrl", "K"] },
  { label: "Esta lista de atalhos", keys: ["?"] }
]
</script>

<template>
  <EditorModalShell
    :open="open"
    title="Atalhos de teclado"
    icon="command-line"
    icon-tone="brand"
    :width="460"
    @close="emit('close')"
  >
    <!-- Grade de atalhos sem rodapé -->
    <div class="shortcuts-grid">
      <div
        v-for="shortcut in shortcuts"
        :key="shortcut.label"
        class="shortcut-row"
      >
        <!-- Label descritivo do atalho -->
        <span class="shortcut-label">{{ shortcut.label }}</span>

        <!-- Teclas do atalho -->
        <div class="shortcut-keys">
          <AppKbd
            v-for="(key, i) in shortcut.keys"
            :key="i"
          >
            {{ key }}
          </AppKbd>
        </div>
      </div>
    </div>
  </EditorModalShell>
</template>

<style scoped>
/* Grade principal de atalhos */
.shortcuts-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 2px;
}

/* Linha de atalho individual */
.shortcut-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 10px 12px;
  background: var(--surface-elevated);
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  gap: 12px;
}

/* Label textual */
.shortcut-label {
  font-size: 13px;
  color: var(--fg-secondary);
  line-height: 1.4;
  flex: 1;
  min-width: 0;
}

/* Grupo de teclas */
.shortcut-keys {
  display: flex;
  align-items: center;
  gap: 4px;
  flex-shrink: 0;
}
</style>
