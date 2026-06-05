<script setup lang="ts">
import { onClickOutside } from "@vueuse/core"
import type { EditorSettings } from "~/types/pipeline-editor-v2"
import { LAYOUT_OPTIONS } from "./constants"

// ---------------------------------------------------------------------------
// Props & emits
// ---------------------------------------------------------------------------
const props = withDefaults(defineProps<{
  settings?: EditorSettings
}>(), {
  settings: () => ({
    layout: "tri_pane",
    density: "comfortable",
    showSessionsRail: true,
    showStateTimeline: true,
  }),
})

const emit = defineEmits<{
  "update:settings": [settings: EditorSettings]
}>()

// ---------------------------------------------------------------------------
// Estado local
// ---------------------------------------------------------------------------
const open = ref(false)
const containerRef = ref<HTMLElement | null>(null)

onClickOutside(containerRef, () => {
  open.value = false
})

// ---------------------------------------------------------------------------
// Helpers para atualizar configurações
// ---------------------------------------------------------------------------
function setLayout(layout: string) {
  emit("update:settings", { ...props.settings, layout: layout as EditorSettings["layout"] })
}

function setDensity(density: "compact" | "comfortable") {
  emit("update:settings", { ...props.settings, density })
}

function setShowSessionsRail(v: boolean) {
  emit("update:settings", { ...props.settings, showSessionsRail: v })
}

function setShowStateTimeline(v: boolean) {
  emit("update:settings", { ...props.settings, showStateTimeline: v })
}

// ---------------------------------------------------------------------------
// Botões demo (visíveis apenas em desenvolvimento)
// ---------------------------------------------------------------------------
const demoJourneys = [
  { label: "Fluxo vazio (idle)", value: "idle" },
  { label: "Gerando proposta", value: "generating_proposal" },
  { label: "Preview rodando", value: "running_preview" },
  { label: "Validando", value: "validating" },
  { label: "PR aberto", value: "pr_created" },
  { label: "Erro", value: "error" },
]
</script>

<template>
  <!-- Container relativo para posicionar o popover -->
  <div ref="containerRef" class="settings-container">
    <!-- Botão disparador -->
    <AppIconBtn
      icon="adjustments-horizontal"
      label="Configurações do editor"
      :size="28"
      :active="open"
      @click="open = !open"
    />

    <!-- Popover de configurações -->
    <Transition name="pop">
      <div v-if="open" class="popover">
        <!-- Cabeçalho -->
        <div class="popover-header">
          <AppIcon name="adjustments-horizontal" size="xs" />
          <span>Configurações do editor</span>
        </div>

        <!-- Seção: layout -->
        <div class="popover-section">
          <span class="section-label">Layout</span>
          <div class="layout-options">
            <button
              v-for="opt in LAYOUT_OPTIONS"
              :key="opt.value"
              class="layout-btn"
              :class="{ active: settings.layout === opt.value }"
              @click="setLayout(opt.value)"
            >
              <div class="layout-radio" :class="{ active: settings.layout === opt.value }">
                <div v-if="settings.layout === opt.value" class="radio-dot" />
              </div>
              <span>{{ opt.label }}</span>
            </button>
          </div>
        </div>

        <div class="popover-divider" />

        <!-- Seção: densidade -->
        <div class="popover-section">
          <span class="section-label">Densidade</span>
          <div class="density-toggle">
            <button
              class="density-btn"
              :class="{ active: settings.density === 'compact' }"
              @click="setDensity('compact')"
            >
              Compacto
            </button>
            <button
              class="density-btn"
              :class="{ active: settings.density === 'comfortable' }"
              @click="setDensity('comfortable')"
            >
              Confortável
            </button>
          </div>
        </div>

        <div class="popover-divider" />

        <!-- Seção: visibilidade de painéis -->
        <div class="popover-section">
          <span class="section-label">Painéis</span>

          <label class="checkbox-row">
            <input
              type="checkbox"
              :checked="settings.showSessionsRail"
              @change="setShowSessionsRail(($event.target as HTMLInputElement).checked)"
            >
            <span>Painel de sessões</span>
          </label>

          <label class="checkbox-row">
            <input
              type="checkbox"
              :checked="settings.showStateTimeline"
              @change="setShowStateTimeline(($event.target as HTMLInputElement).checked)"
            >
            <span>Timeline de estado</span>
          </label>
        </div>

        <!-- Seção dev-only: atalhos de demo -->
        <template v-if="$nuxt?.isDev ?? false">
          <div class="popover-divider" />
          <div class="popover-section">
            <span class="section-label dev-badge">Dev — Jump-to demo</span>
            <div class="demo-btns">
              <AppButton
                v-for="j in demoJourneys"
                :key="j.value"
                variant="ghost"
                color="neutral"
                size="xs"
                :block="true"
              >
                {{ j.label }}
              </AppButton>
            </div>
          </div>
        </template>
      </div>
    </Transition>
  </div>
</template>

<style scoped>
/* Container relativo */
.settings-container {
  position: relative;
}

/* Popover */
.popover {
  position: absolute;
  bottom: calc(100% + 8px);
  right: 0;
  width: 280px;
  border-radius: var(--radius-lg);
  border: 1px solid var(--border);
  background: var(--surface);
  box-shadow: var(--shadow-medium);
  z-index: 40;
  overflow: hidden;
}

/* Transição de abertura */
.pop-enter-active,
.pop-leave-active {
  transition: opacity 0.15s ease, transform 0.15s ease;
}

.pop-enter-from,
.pop-leave-to {
  opacity: 0;
  transform: translateY(4px) scale(0.98);
}

/* Cabeçalho do popover */
.popover-header {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 10px 12px 8px;
  border-bottom: 1px solid var(--border);
  font-size: 12px;
  font-weight: 600;
  color: var(--fg-secondary);
}

/* Seções */
.popover-section {
  padding: 10px 12px;
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.section-label {
  font-size: 10px;
  font-weight: 700;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  color: var(--fg-tertiary);
}

.section-label.dev-badge {
  color: var(--brand-400);
}

.popover-divider {
  height: 1px;
  background: var(--border);
}

/* Opções de layout */
.layout-options {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.layout-btn {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 8px;
  border-radius: var(--radius-sm);
  border: none;
  background: transparent;
  cursor: pointer;
  color: var(--fg-primary);
  font-size: 13px;
  text-align: left;
  width: 100%;
  transition: background 0.12s;
}

.layout-btn:hover {
  background: var(--surface-elevated);
}

.layout-btn.active {
  color: var(--brand-500);
}

/* Radio visual */
.layout-radio {
  width: 14px;
  height: 14px;
  border-radius: 50%;
  border: 1.5px solid var(--border);
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  transition: border-color 0.12s;
}

.layout-radio.active {
  border-color: var(--brand-500);
}

.radio-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: var(--brand-500);
}

/* Toggle de densidade */
.density-toggle {
  display: flex;
  border-radius: var(--radius-md);
  border: 1px solid var(--border);
  overflow: hidden;
}

.density-btn {
  flex: 1;
  padding: 5px 8px;
  border: none;
  background: transparent;
  cursor: pointer;
  font-size: 12px;
  color: var(--fg-secondary);
  transition: background 0.12s, color 0.12s;
}

.density-btn + .density-btn {
  border-left: 1px solid var(--border);
}

.density-btn.active {
  background: var(--brand-500);
  color: #fff;
}

/* Checkboxes */
.checkbox-row {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
  color: var(--fg-primary);
  cursor: pointer;
  padding: 2px 0;
}

.checkbox-row input[type="checkbox"] {
  width: 14px;
  height: 14px;
  accent-color: var(--brand-500);
  cursor: pointer;
}

/* Botões demo */
.demo-btns {
  display: flex;
  flex-direction: column;
  gap: 2px;
}
</style>
