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
import { useCustomEndpoints } from "~/composables/useCustomEndpoints"
import { useCombinedProviders, useLLMProviders } from "~/composables/useLLMProviders"

const props = defineProps<{
  /** Provider id atual (anthropic/openai/google) ou "custom:<uuid>" ou "" pra default */
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

const { findModel, formatPrice } = useLLMProviders()
const { endpoints, load: loadEndpoints } = useCustomEndpoints()
const { combined, findById } = useCombinedProviders(endpoints)

onMounted(() => {
  if (!endpoints.value.length) loadEndpoints()
})

const providers = combined  // dropdown agora inclui custom

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
  const p = findById(localProvider.value)
  return p?.models || []
})

const selectedModel = computed(() => {
  if (!localProvider.value || !localModel.value) return undefined
  // Built-in: usa findModel pra ter pricing
  if (!localProvider.value.startsWith("custom:")) {
    return findModel(localProvider.value, localModel.value)
  }
  return undefined  // custom nao tem pricing standard
})

const selectStyle = {
  background: "var(--surface)",
  borderColor: "var(--border)",
  color: "var(--text-primary)",
}

function onProviderChange() {
  // Auto-pick primeiro model do novo provider (custom ou built-in)
  const p = findById(localProvider.value)
  if (p && p.models.length) {
    localModel.value = p.models[0]?.id || ""
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
