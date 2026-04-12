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
        :placeholder="isConfigured ? '••••••••' : 'Cole sua chave aqui'"
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
defineProps<{
  label: string
  type: string
  isConfigured?: boolean
  isValid?: boolean
}>()

defineEmits<{
  save: [value: string]
  test: []
}>()

const value = ref("")
const showValue = ref(false)
</script>
