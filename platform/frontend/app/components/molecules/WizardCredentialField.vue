<template>
  <div
    class="rounded-[var(--radius-md)] border p-3"
    :style="{
      borderColor: override ? 'var(--brand-500)' : 'var(--border)',
      background: 'var(--surface)',
    }"
  >
    <div class="flex items-center justify-between mb-1.5">
      <div class="flex items-center gap-2">
        <label
          class="text-xs font-medium"
          :style="{ color: 'var(--text-primary)' }"
        >
          {{ label }}{{ required ? " *" : "" }}
        </label>
        <span
          v-if="companyConfigured && !override"
          class="inline-flex items-center gap-1 text-[10px] px-1.5 py-0.5 rounded-full"
          :style="{
            background: 'rgba(127,34,254,0.15)',
            color: 'var(--brand-400)',
          }"
        >
          <AppIcon name="check-circle" size="xs" />
          Usando credencial da empresa
        </span>
        <span
          v-else-if="override"
          class="inline-flex items-center gap-1 text-[10px] px-1.5 py-0.5 rounded-full"
          :style="{
            background: 'rgba(251,191,36,0.15)',
            color: 'rgb(251,191,36)',
          }"
        >
          Override deste deploy
        </span>
        <span
          v-else
          class="inline-flex items-center gap-1 text-[10px] px-1.5 py-0.5 rounded-full"
          :style="{
            background: 'rgba(239,68,68,0.12)',
            color: 'var(--status-error)',
          }"
        >
          Nao configurada
        </span>
      </div>
      <button
        v-if="companyConfigured"
        type="button"
        class="text-[10px] underline"
        :style="{ color: 'var(--text-tertiary)' }"
        @click="toggleOverride"
      >
        {{ override ? "Usar padrao da empresa" : "Sobrescrever" }}
      </button>
    </div>

    <AppInput
      v-if="override || !companyConfigured"
      :model-value="modelValue"
      :type="inputType"
      :placeholder="placeholder"
      :helper="helper"
      @update:model-value="(v: string) => emit('update:modelValue', v)"
    />
    <p
      v-else
      class="text-[11px]"
      :style="{ color: 'var(--text-tertiary)' }"
    >
      Valor configurado em /settings sera usado neste deploy.
    </p>
  </div>
</template>

<script setup lang="ts">
const props = withDefaults(
  defineProps<{
    label: string
    modelValue: string
    companyConfigured: boolean
    inputType?: "text" | "password" | "url"
    placeholder?: string
    helper?: string
    required?: boolean
  }>(),
  {
    inputType: "text",
    placeholder: "",
    helper: "",
    required: false,
  },
)

const emit = defineEmits<{
  "update:modelValue": [value: string]
}>()

// Override default:
// - Se a empresa tem a credencial configurada → false (usa padrao)
// - Se NAO tem → true (obriga input)
const override = ref(!props.companyConfigured)

// Se a credencial da empresa aparecer depois do mount (ex: /settings load
// assincrono terminou), volta a usar o padrao a nao ser que o user ja tenha
// digitado algo.
watch(
  () => props.companyConfigured,
  (newVal, oldVal) => {
    if (newVal && !oldVal && !props.modelValue) {
      override.value = false
    }
  },
)

function toggleOverride() {
  override.value = !override.value
  if (!override.value) {
    // voltando ao padrao — limpa o valor override digitado
    emit("update:modelValue", "")
  }
}
</script>
