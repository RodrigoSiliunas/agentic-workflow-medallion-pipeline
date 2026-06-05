<template>
  <!-- Backdrop do modal expandido -->
  <Teleport to="body">
    <div
      v-if="open"
      class="modal-backdrop"
      @click="emit('close')"
    >
      <!-- Container interno — para propagação para não fechar ao clicar dentro -->
      <div class="modal-inner" @click.stop>
        <!-- Cabeçalho -->
        <header class="modal-header">
          <div class="flex items-center gap-[10px]">
            <AppIcon
              name="arrows-pointing-out"
              size="sm"
              :style="{ color: 'var(--brand-400)' }"
            />
            <h3 class="modal-title">{{ title }}</h3>
          </div>
          <div class="flex flex-1 items-center justify-end gap-[8px]">
            <!-- Ação de exportar opcional -->
            <AppButton
              v-if="onExport"
              variant="outline"
              color="neutral"
              size="sm"
              icon="arrow-down-tray"
              @click="onExport()"
            >
              Exportar
            </AppButton>
            <AppIconBtn
              icon="x-mark"
              label="Fechar modal expandido"
              :size="28"
              @click="emit('close')"
            />
          </div>
        </header>

        <!-- Corpo com slot -->
        <div class="modal-body">
          <slot />
        </div>
      </div>
    </div>
  </Teleport>
</template>

<script setup lang="ts">
import { useEventListener } from "@vueuse/core"

const props = withDefaults(
  defineProps<{
    open: boolean
    title: string
    onExport?: (() => void) | null
  }>(),
  {
    onExport: null,
  },
)

const emit = defineEmits<{
  close: []
}>()

// Fecha ao pressionar Escape
useEventListener("keydown", (e: KeyboardEvent) => {
  if (e.key === "Escape" && props.open) {
    emit("close")
  }
})
</script>

<style scoped>
.modal-backdrop {
  position: fixed;
  inset: 0;
  z-index: 300;
  background: rgba(9, 10, 11, 0.8);
  backdrop-filter: blur(4px);
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 32px;
  animation: fade-in 180ms ease-out;
}

.modal-inner {
  max-width: 1280px;
  width: 100%;
  max-height: calc(100vh - 64px);
  display: flex;
  flex-direction: column;
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius-xl);
  box-shadow: var(--shadow-medium);
  overflow: hidden;
  animation: modal-pop 200ms ease-out;
}

.modal-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 14px 18px;
  border-bottom: 1px solid var(--border);
  gap: 12px;
  flex-shrink: 0;
}

.modal-title {
  font-size: 14px;
  font-weight: 600;
  color: var(--fg-primary);
  margin: 0;
}

.modal-body {
  flex: 1;
  overflow: auto;
  padding: 18px;
}

@keyframes fade-in {
  from { opacity: 0; }
  to { opacity: 1; }
}

@keyframes modal-pop {
  from { opacity: 0; transform: scale(0.97) translateY(6px); }
  to { opacity: 1; transform: scale(1) translateY(0); }
}
</style>
