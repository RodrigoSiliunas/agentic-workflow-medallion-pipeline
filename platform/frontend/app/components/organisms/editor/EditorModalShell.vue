<script setup lang="ts">
import { useEventListener } from "@vueuse/core"

// Props e emits do shell genérico de modais do editor
const props = withDefaults(
  defineProps<{
    open: boolean
    width?: number
    title: string
    icon?: string
    iconTone?: "brand" | "warning" | "error" | "success"
  }>(),
  {
    width: 520,
    icon: undefined,
    iconTone: "brand"
  }
)

const emit = defineEmits<{
  close: []
}>()

const slots = useSlots()

// Mapa de cores para cada tom do ícone
const iconColors: Record<string, { bg: string; fg: string }> = {
  brand: { bg: "rgba(142,81,246,0.15)", fg: "var(--brand-400)" },
  warning: { bg: "rgba(245,158,11,0.15)", fg: "var(--status-warning)" },
  error: { bg: "rgba(239,68,68,0.15)", fg: "var(--status-error)" },
  success: { bg: "rgba(34,197,94,0.15)", fg: "var(--status-success)" }
}

const iconColor = computed(() => iconColors[props.iconTone] ?? iconColors.brand)

// Referência do container do diálogo para focus trap
const dialogRef = ref<HTMLElement | null>(null)
let previousFocus: HTMLElement | null = null

// Seleciona todos os elementos focáveis dentro do modal
function getFocusable(el: HTMLElement): HTMLElement[] {
  return Array.from(
    el.querySelectorAll<HTMLElement>(
      'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])'
    )
  ).filter((e) => !e.hasAttribute("disabled"))
}

// Ao abrir: salva foco anterior e foca no primeiro elemento do modal
watch(
  () => props.open,
  (val) => {
    if (val) {
      previousFocus = document.activeElement as HTMLElement | null
      nextTick(() => {
        if (dialogRef.value) {
          const focusable = getFocusable(dialogRef.value)
          focusable[0]?.focus()
        }
      })
    } else {
      previousFocus?.focus()
    }
  }
)

// Fecha ao pressionar Escape
useEventListener("keydown", (e: KeyboardEvent) => {
  if (e.key === "Escape" && props.open) {
    emit("close")
  }
})
</script>

<template>
  <div
    v-if="open"
    class="modal-backdrop"
    role="dialog"
    aria-modal="true"
    :aria-label="title"
    @click.self="emit('close')"
  >
    <!-- Container do modal com stop de propagação -->
    <div
      ref="dialogRef"
      class="modal-container"
      :style="{ width: width + 'px' }"
      @click.stop
    >
      <!-- Cabeçalho do modal -->
      <header class="modal-header">
        <div class="modal-header-left">
          <!-- Ícone decorativo opcional -->
          <div
            v-if="icon"
            class="modal-icon-box"
            :style="{ background: iconColor.bg }"
          >
            <AppIcon
              :name="icon"
              size="sm"
              :style="{ color: iconColor.fg }"
            />
          </div>
          <h2 class="modal-title">{{ title }}</h2>
        </div>
        <AppIconBtn
          icon="x-mark"
          label="Fechar"
          :size="28"
          @click="emit('close')"
        />
      </header>

      <!-- Corpo do modal com scroll -->
      <div class="modal-body">
        <slot />
      </div>

      <!-- Rodapé opcional -->
      <footer v-if="slots.footer" class="modal-footer">
        <slot name="footer" />
      </footer>
    </div>
  </div>
</template>

<style scoped>
/* Backdrop com blur */
.modal-backdrop {
  position: fixed;
  inset: 0;
  background: rgba(9, 10, 11, 0.75);
  backdrop-filter: blur(4px);
  z-index: 100;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 24px;
  animation: fade-in 200ms ease-out;
}

/* Container principal do modal */
.modal-container {
  max-width: 100%;
  max-height: calc(100vh - 48px);
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius-xl);
  box-shadow: var(--shadow-medium);
  display: flex;
  flex-direction: column;
  animation: modal-pop 200ms ease-out;
  overflow: hidden;
}

/* Cabeçalho */
.modal-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 16px 18px 14px;
  border-bottom: 1px solid var(--border);
  gap: 12px;
  flex-shrink: 0;
}

.modal-header-left {
  display: flex;
  align-items: center;
  gap: 12px;
  min-width: 0;
}

/* Caixa do ícone decorativo */
.modal-icon-box {
  width: 32px;
  height: 32px;
  border-radius: var(--radius-md);
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.modal-title {
  font-size: 15px;
  font-weight: 600;
  color: var(--fg-primary);
  margin: 0;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

/* Corpo com scroll */
.modal-body {
  flex: 1;
  overflow-y: auto;
  padding: 16px 18px;
}

/* Rodapé */
.modal-footer {
  padding: 12px 18px;
  border-top: 1px solid var(--border);
  background: var(--surface-elevated);
  flex-shrink: 0;
}

/* Animações */
@keyframes fade-in {
  from {
    opacity: 0;
  }
  to {
    opacity: 1;
  }
}

@keyframes modal-pop {
  from {
    opacity: 0;
    transform: scale(0.95) translateY(8px);
  }
  to {
    opacity: 1;
    transform: scale(1) translateY(0);
  }
}
</style>
