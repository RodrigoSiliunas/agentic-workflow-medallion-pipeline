<template>
  <div class="space-y-2">
    <div v-if="label" class="text-xs font-medium" :style="{ color: 'var(--text-secondary)' }">
      {{ label }}
    </div>

    <div class="flex gap-2 items-center">
      <!-- Provider dropdown -->
      <select
        v-model="localProvider"
        class="flex-1 px-2.5 py-1.5 rounded-[var(--radius-sm)] border text-xs"
        :style="selectStyle"
        @change="onProviderChange"
      >
        <option v-if="allowDefault" value="">— default empresa —</option>
        <option v-for="p in providers" :key="p.id" :value="p.id">
          {{ p.label }}
        </option>
      </select>

      <!-- Model dropdown (contextual) -->
      <select
        v-model="localModel"
        class="flex-1 px-2.5 py-1.5 rounded-[var(--radius-sm)] border text-xs"
        :style="selectStyle"
        :disabled="!localProvider && !allowDefault"
        @change="emitChange"
      >
        <option v-if="allowDefault" value="">— default —</option>
        <option v-for="m in availableModels" :key="m.id" :value="m.id">
          {{ m.label }}
        </option>
      </select>
    </div>

    <!-- Pricing helper (se model selecionado) -->
    <div v-if="selectedModel" class="text-[10px]" :style="{ color: 'var(--text-tertiary)' }">
      {{ formatPrice(selectedModel) }} · contexto {{ (selectedModel.contextWindow / 1000).toFixed(0) }}k tokens
    </div>
  </div>
</template>

<script setup lang="ts">
import { useLLMProviders } from "~/composables/useLLMProviders"

const props = defineProps<{
  /** Provider id atual (anthropic/openai/google) ou "" pra default */
  modelValueProvider?: string
  /** Model id atual ou "" pra default */
  modelValueModel?: string
  /** Label acima do dropdown */
  label?: string
  /** Se true, mostra opcao "— default —" no inicio */
  allowDefault?: boolean
}>()

const emit = defineEmits<{
  "update:modelValueProvider": [value: string]
  "update:modelValueModel": [value: string]
  change: [provider: string, model: string]
}>()

const { providers, findProvider, findModel, formatPrice } = useLLMProviders()

const localProvider = ref(props.modelValueProvider || "")
const localModel = ref(props.modelValueModel || "")

watch(
  () => props.modelValueProvider,
  (v) => (localProvider.value = v || ""),
)
watch(
  () => props.modelValueModel,
  (v) => (localModel.value = v || ""),
)

const availableModels = computed(() => {
  const p = findProvider(localProvider.value)
  return p?.models || []
})

const selectedModel = computed(() => {
  if (!localProvider.value || !localModel.value) return undefined
  return findModel(localProvider.value, localModel.value)
})

const selectStyle = {
  background: "var(--surface)",
  borderColor: "var(--border)",
  color: "var(--text-primary)",
}

function onProviderChange() {
  // Auto-pick balanced model do novo provider
  const p = findProvider(localProvider.value)
  if (p) {
    const balanced = p.models.find((m) => m.tier === "balanced") || p.models[0]
    if (balanced) localModel.value = balanced.id
  } else {
    localModel.value = ""
  }
  emitChange()
}

function emitChange() {
  emit("update:modelValueProvider", localProvider.value)
  emit("update:modelValueModel", localModel.value)
  emit("change", localProvider.value, localModel.value)
}
</script>
