<script setup lang="ts">
import { onClickOutside } from "@vueuse/core"
import type { ModelProvider } from "~/types/pipeline-editor-v2"
import { MODEL_PROVIDERS } from "./constants"

// Seletor de provedor/modelo de LLM usado no compositor
const props = withDefaults(defineProps<{
  providerId?: string
  modelId?: string
}>(), {
  providerId: "anthropic",
  modelId: "claude-sonnet-4.6",
})

const emit = defineEmits<{
  change: [providerId: string, modelId: string]
}>()

const open = ref(false)
const containerRef = ref<HTMLElement | null>(null)

onClickOutside(containerRef, () => {
  open.value = false
})

// Provedor e modelo ativos
const activeProvider = computed<ModelProvider | undefined>(() =>
  MODEL_PROVIDERS.find((p) => p.id === props.providerId)
)

const activeModel = computed(() =>
  activeProvider.value?.models.find((m) => m.id === props.modelId)
)

// Label curto — remove prefixos verbosos
function shortLabel(label: string): string {
  return label.replace(/^Claude\s+/i, "").replace(/^GPT-/i, "GPT-")
}

function selectModel(providerId: string, modelId: string) {
  emit("change", providerId, modelId)
  open.value = false
}
</script>

<template>
  <div ref="containerRef" class="model-picker">
    <!-- Botão gatilho -->
    <button
      class="trigger-btn"
      type="button"
      :aria-expanded="open"
      aria-haspopup="menu"
      @click="open = !open"
    >
      <AppIcon
        v-if="activeProvider"
        :name="activeProvider.iconName"
        size="xs"
        style="color: var(--brand-400)"
      />
      <span class="trigger-model">{{ activeModel ? shortLabel(activeModel.label) : modelId }}</span>
      <span class="trigger-dot">·</span>
      <span class="trigger-provider">{{ activeProvider?.name ?? providerId }}</span>
      <AppIcon name="chevron-down" size="xs" />
    </button>

    <!-- Dropdown -->
    <div v-if="open" class="dropdown" role="menu">
      <div class="dropdown-scroll">
        <template v-for="(provider, pIdx) in MODEL_PROVIDERS" :key="provider.id">
          <!-- Cabeçalho do provedor -->
          <div class="provider-header" :class="{ 'provider-header--sep': pIdx > 0 }">
            <AppIcon :name="provider.iconName" size="xs" />
            <span class="provider-name">{{ provider.name }}</span>
          </div>

          <!-- Modelos do provedor -->
          <button
            v-for="model in provider.models"
            :key="model.id"
            class="model-item"
            :class="{ 'model-item--active': provider.id === providerId && model.id === modelId }"
            role="menuitem"
            type="button"
            @click="selectModel(provider.id, model.id)"
          >
            <div class="model-item__left">
              <span class="model-item__label">{{ model.label }}</span>
              <AppPill v-if="model.default" tone="brand" size="xs">padrão</AppPill>
            </div>
            <span class="model-item__hint">{{ model.hint }}</span>
            <AppIcon
              v-if="provider.id === providerId && model.id === modelId"
              name="check"
              size="xs"
              class="model-item__check"
            />
          </button>
        </template>
      </div>
    </div>
  </div>
</template>

<style scoped>
.model-picker {
  position: relative;
}

/* Botão gatilho */
.trigger-btn {
  display: flex;
  align-items: center;
  gap: 6px;
  height: 26px;
  padding: 4px 8px;
  border-radius: var(--radius-md);
  border: 1px solid var(--border);
  background: var(--surface-elevated);
  cursor: pointer;
  font-family: var(--font-sans);
  font-size: 11px;
  color: var(--fg-primary);
  transition: background 0.15s;
  white-space: nowrap;
}

.trigger-btn:hover {
  background: var(--surface);
}

.trigger-model {
  font-weight: 600;
}

.trigger-dot,
.trigger-provider {
  color: var(--fg-tertiary);
}

/* Dropdown */
.dropdown {
  position: absolute;
  bottom: calc(100% + 6px);
  right: 0;
  width: 280px;
  border-radius: var(--radius-lg);
  border: 1px solid var(--border);
  background: var(--surface);
  box-shadow: var(--shadow-medium);
  overflow: hidden;
  z-index: 50;
}

.dropdown-scroll {
  max-height: 360px;
  overflow-y: auto;
}

/* Cabeçalho do provedor */
.provider-header {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 8px 12px 4px;
}

.provider-header--sep {
  border-top: 1px solid var(--border);
}

.provider-name {
  font-family: var(--font-sans);
  font-size: 10px;
  font-weight: 700;
  letter-spacing: 0.07em;
  text-transform: uppercase;
  color: var(--fg-tertiary);
}

/* Item de modelo */
.model-item {
  display: flex;
  flex-direction: row;
  align-items: center;
  gap: 8px;
  width: 100%;
  padding: 8px 12px;
  background: transparent;
  border: none;
  cursor: pointer;
  text-align: left;
  transition: background 0.1s;
}

.model-item:hover {
  background: var(--surface-elevated);
}

.model-item--active {
  background: var(--surface-elevated);
}

.model-item__left {
  display: flex;
  align-items: center;
  gap: 6px;
  flex: 1;
  min-width: 0;
}

.model-item__label {
  font-family: var(--font-sans);
  font-size: 12px;
  font-weight: 500;
  color: var(--fg-primary);
  white-space: nowrap;
}

.model-item__hint {
  font-family: var(--font-sans);
  font-size: 11px;
  color: var(--fg-tertiary);
  flex: 1;
  text-align: right;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.model-item__check {
  color: var(--brand-400);
  flex-shrink: 0;
}
</style>
