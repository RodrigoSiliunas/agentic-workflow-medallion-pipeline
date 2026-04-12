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

        <!-- Model selector -->
        <div class="relative" ref="dropdownRef">
          <button
            type="button"
            class="flex items-center gap-1 px-2 py-1.5 rounded-[var(--radius-md)] text-[11px] font-medium transition-colors hover:bg-[var(--surface-elevated)]"
            :style="{ color: 'var(--text-secondary)' }"
            @click="showModelPicker = !showModelPicker"
          >
            <span>{{ selectedModel.short }}</span>
            <AppIcon name="chevron-down" size="xs" />
          </button>

          <!-- Dropdown -->
          <div
            v-if="showModelPicker"
            class="absolute bottom-full right-0 mb-2 w-56 rounded-[var(--radius-lg)] border shadow-lg overflow-hidden z-50"
            :style="{ borderColor: 'var(--border)', background: 'var(--surface)' }"
          >
            <button
              v-for="m in MODELS"
              :key="m.id"
              type="button"
              class="w-full flex items-start gap-3 px-3 py-2.5 text-left transition-colors hover:bg-[var(--surface-elevated)]"
              @click="selectModel(m.id)"
            >
              <div class="flex-1 min-w-0">
                <div class="flex items-center gap-2">
                  <span class="text-xs font-semibold" :style="{ color: 'var(--text-primary)' }">
                    {{ m.short }}
                  </span>
                  <AppIcon
                    v-if="m.id === modelId"
                    name="check"
                    size="xs"
                    class="text-[var(--brand-500)]"
                  />
                </div>
                <p class="text-[10px] mt-0.5" :style="{ color: 'var(--text-tertiary)' }">
                  {{ m.description }}
                </p>
              </div>
            </button>
          </div>
        </div>

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
const MODELS = [
  {
    id: "opus",
    short: "Opus 4.6",
    description: "Mais capaz para analises complexas",
    apiModel: "claude-opus-4-20250514",
  },
  {
    id: "sonnet",
    short: "Sonnet 4.6",
    description: "Equilibrio entre velocidade e qualidade",
    apiModel: "claude-sonnet-4-20250514",
  },
  {
    id: "haiku",
    short: "Haiku 4.5",
    description: "Mais rapido para respostas simples",
    apiModel: "claude-haiku-4-5-20251001",
  },
] as const

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

const emit = defineEmits<{
  send: [content: string]
  "update:model": [modelId: string]
}>()

const isMock = Boolean(useRuntimeConfig().public.mockMode)
const value = ref("")
const textarea = ref<HTMLTextAreaElement | null>(null)
const showModelPicker = ref(false)
const modelId = ref("sonnet")
const dropdownRef = ref<HTMLElement | null>(null)

const selectedModel = computed(() => MODELS.find((m) => m.id === modelId.value) || MODELS[1])

const canSubmit = computed(() => !props.disabled && value.value.trim().length > 0)

function selectModel(id: string) {
  modelId.value = id
  showModelPicker.value = false
  emit("update:model", id)
}

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

// Fechar dropdown ao clicar fora
function onClickOutside(e: MouseEvent) {
  if (dropdownRef.value && !dropdownRef.value.contains(e.target as Node)) {
    showModelPicker.value = false
  }
}

onMounted(() => {
  autoResize()
  document.addEventListener("click", onClickOutside)
})

onUnmounted(() => {
  document.removeEventListener("click", onClickOutside)
})
</script>
