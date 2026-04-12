<template>
  <header
    class="flex items-center justify-between gap-3 px-6 py-3 border-b"
    :style="{ borderColor: 'var(--border)' }"
  >
    <div class="flex items-center gap-3 min-w-0">
      <div
        class="w-8 h-8 rounded-[var(--radius-md)] flex items-center justify-center flex-shrink-0"
        :style="{ background: 'var(--brand-600)' }"
      >
        <AppIcon name="cpu-chip" size="sm" class="text-white" />
      </div>
      <div class="min-w-0">
        <div class="flex items-center gap-2">
          <h2
            class="text-sm font-semibold truncate"
            :style="{ color: 'var(--text-primary)' }"
          >
            {{ pipeline?.name ?? "Pipeline" }}
          </h2>
          <StatusBadge v-if="pipeline" :status="pipeline.status" />
        </div>
        <p
          v-if="threadTitle"
          class="text-[11px] truncate"
          :style="{ color: 'var(--text-tertiary)' }"
        >
          {{ threadTitle }}
        </p>
      </div>
    </div>

    <div class="flex items-center gap-1 flex-shrink-0">
      <AppButton
        variant="ghost"
        size="sm"
        icon="i-heroicons-arrow-path"
        square
        title="Recarregar mensagens"
        @click="$emit('refresh')"
      />

      <div ref="menuRef" class="relative">
        <AppButton
          variant="ghost"
          size="sm"
          icon="i-heroicons-ellipsis-horizontal"
          square
          @click="showMenu = !showMenu"
        />
        <div
          v-if="showMenu"
          class="absolute right-0 top-full mt-1 w-48 rounded-[var(--radius-md)] border shadow-lg z-50 py-1"
          :style="{ background: 'var(--surface)', borderColor: 'var(--border)' }"
        >
          <button
            class="w-full flex items-center gap-2 px-3 py-2 text-xs text-left transition-colors hover:bg-[var(--surface-elevated)]"
            :style="{ color: 'var(--text-secondary)' }"
            @click="copyThreadId"
          >
            <AppIcon name="clipboard-document" size="xs" />
            Copiar Thread ID
          </button>
          <button
            class="w-full flex items-center gap-2 px-3 py-2 text-xs text-left transition-colors hover:bg-[var(--surface-elevated)]"
            :style="{ color: 'var(--text-secondary)' }"
            @click="$emit('clear'); showMenu = false"
          >
            <AppIcon name="trash" size="xs" />
            Limpar conversa
          </button>
        </div>
      </div>
    </div>
  </header>
</template>

<script setup lang="ts">
import type { Pipeline } from "~/types/pipeline"

const props = defineProps<{
  pipeline: Pipeline | null
  threadTitle?: string
  threadId?: string
}>()

defineEmits<{
  refresh: []
  clear: []
}>()

const showMenu = ref(false)
const menuRef = ref<HTMLElement | null>(null)

function copyThreadId() {
  if (props.threadId) {
    navigator.clipboard.writeText(props.threadId)
  }
  showMenu.value = false
}

function onClickOutside(e: MouseEvent) {
  if (menuRef.value && !menuRef.value.contains(e.target as Node)) {
    showMenu.value = false
  }
}

onMounted(() => document.addEventListener("click", onClickOutside))
onUnmounted(() => document.removeEventListener("click", onClickOutside))
</script>
