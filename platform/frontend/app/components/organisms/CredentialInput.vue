<template>
  <div
    class="p-4 rounded-[var(--radius-lg)]"
    :style="{ background: 'var(--surface)', border: '1px solid var(--border)' }"
  >
    <div class="flex items-center justify-between mb-2">
      <h3 class="font-medium text-sm">{{ label }}</h3>
      <div class="flex items-center gap-2">
        <span
          v-if="isConfigured"
          class="text-[10px] px-2 py-0.5 rounded-full"
          :style="{
            background: isValid ? 'rgba(34,197,94,0.1)' : 'rgba(239,68,68,0.1)',
            color: isValid ? 'var(--status-success)' : 'var(--status-error)',
          }"
        >
          {{ isValid ? 'Válido' : 'Configurado' }}
        </span>
        <span v-else class="text-[10px]" style="color: var(--text-tertiary)">Não configurado</span>
      </div>
    </div>

    <div class="flex gap-2">
      <UInput
        v-model="value"
        :type="showValue ? 'text' : 'password'"
        :placeholder="isConfigured ? '••••••••' : effectivePlaceholder"
        class="flex-1"
        size="sm"
      />
      <UButton variant="ghost" size="sm" icon="i-heroicons-eye" @click="showValue = !showValue" />
      <UButton size="sm" :disabled="!value" @click="$emit('save', value); value = ''">Salvar</UButton>
      <UButton v-if="isConfigured" variant="outline" size="sm" @click="$emit('test')">Testar</UButton>
    </div>
  </div>
</template>

<script setup lang="ts">
const props = defineProps<{
  label: string
  type: string
  isConfigured?: boolean
  isValid?: boolean
  placeholder?: string
}>()

// Placeholder padrão por tipo — evita "Cole sua chave aqui" em campos que não são chave
const DEFAULT_PLACEHOLDERS: Record<string, string> = {
  github_repo: "owner/repo",
  aws_region: "us-east-2",
  databricks_host: "https://<workspace>.cloud.databricks.com",
  databricks_account_id: "00000000-0000-0000-0000-000000000000",
  databricks_oauth_client_id: "00000000-0000-0000-0000-000000000000",
  databricks_oauth_secret: "dosed1d9b69...",
}

const effectivePlaceholder = computed(
  () => props.placeholder ?? DEFAULT_PLACEHOLDERS[props.type] ?? "Cole o valor aqui",
)

defineEmits<{
  save: [value: string]
  test: []
}>()

const value = ref("")
const showValue = ref(false)
</script>
