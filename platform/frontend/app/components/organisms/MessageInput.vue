<template>
  <div class="px-4 sm:px-6 pb-4">
    <div class="max-w-3xl mx-auto">
      <form
        class="flex items-end gap-2 rounded-[var(--radius-xl)] border border-[var(--border)] bg-[var(--surface)] px-3 py-2 transition-colors focus-within:border-[var(--brand-500)]/50 focus-within:shadow-[var(--shadow-focus)]"
        @submit.prevent="submit"
      >
        <textarea
          ref="textarea"
          v-model="value"
          :placeholder="placeholder"
          :disabled="disabled"
          rows="1"
          class="flex-1 bg-transparent resize-none text-sm leading-relaxed outline-none placeholder:text-[var(--text-tertiary)] max-h-40 py-1.5 px-1"
          :style="{ color: 'var(--text-primary)' }"
          @input="autoResize"
          @keydown.enter.exact.prevent="submit"
          @keydown.shift.enter.exact="onShiftEnter"
        />
        <AppButton
          type="submit"
          icon="i-heroicons-arrow-up"
          size="sm"
          :disabled="!canSubmit"
          :loading="disabled"
          square
        />
      </form>
      <p class="mt-2 text-[10px] text-center" :style="{ color: 'var(--text-tertiary)' }">
        {{ isMock ? 'Modo mock ativo.' : 'Modo ativo.' }} Enter envia, Shift+Enter quebra linha.
      </p>
    </div>
  </div>
</template>

<script setup lang="ts">
const props = withDefaults(
  defineProps<{
    disabled?: boolean
    placeholder?: string
  }>(),
  {
    disabled: false,
    placeholder: "Envie uma mensagem para o agente...",
  },
)

const emit = defineEmits<{ send: [content: string] }>()

const isMock = Boolean(useRuntimeConfig().public.mockMode)
const value = ref("")
const textarea = ref<HTMLTextAreaElement | null>(null)

const canSubmit = computed(() => !props.disabled && value.value.trim().length > 0)

function autoResize() {
  const el = textarea.value
  if (!el) return
  el.style.height = "auto"
  el.style.height = `${Math.min(el.scrollHeight, 160)}px`
}

function submit() {
  if (!canSubmit.value) return
  emit("send", value.value.trim())
  value.value = ""
  nextTick(() => autoResize())
}

function onShiftEnter() {
  // shift+enter deixa o <textarea> inserir quebra de linha
}

onMounted(() => autoResize())
</script>
