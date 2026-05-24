<template>
  <div class="flex gap-2">
    <AppButton variant="outline" size="sm" :disabled="disabled" @click="emit('export', 'csv')">
      Exportar CSV
    </AppButton>
    <AppButton variant="outline" size="sm" :disabled="disabled" @click="emit('export', 'parquet')">
      Exportar Parquet
    </AppButton>
  </div>
</template>

<script setup lang="ts">
defineProps<{ disabled?: boolean }>()

const emit = defineEmits<{
  export: [format: "csv" | "parquet"]
}>()
</script>
