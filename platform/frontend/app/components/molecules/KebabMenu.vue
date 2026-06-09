<template>
  <div class="relative inline-block">
    <!-- Trigger button -->
    <button
      ref="btnRef"
      type="button"
      aria-label="Mais opções"
      title="Mais opções"
      class="inline-flex items-center justify-center rounded-[var(--radius-sm)] border border-transparent transition-colors duration-100 focus-visible:outline-none focus-visible:shadow-[var(--shadow-focus)]"
      :class="[
        sizeClass,
        open
          ? 'border-transparent bg-[var(--surface-elevated)] text-[var(--brand-400)]'
          : 'bg-transparent text-[var(--fg-secondary)] hover:bg-[var(--surface-elevated)] hover:text-[var(--fg-primary)]',
      ]"
      :aria-expanded="open"
      :aria-haspopup="true"
      @click="toggleOpen"
    >
      <AppIcon name="ellipsis-horizontal" size="sm" />
    </button>

    <!-- Dropdown portal -->
    <Teleport to="body">
      <div
        v-if="open"
        ref="menuRef"
        role="menu"
        class="fixed z-[200] overflow-hidden rounded-[var(--radius-lg)] border border-[var(--border)] bg-[var(--surface)] p-1 shadow-[var(--shadow-medium)]"
        :style="{ top: `${pos.top}px`, left: `${pos.left}px`, width: '200px' }"
      >
        <button
          v-for="(item, i) in items"
          :key="i"
          type="button"
          role="menuitem"
          class="flex w-full items-center gap-2 rounded-[var(--radius-sm)] border-none px-[10px] py-2 text-left text-[12px] transition-colors duration-100 hover:bg-[var(--surface-elevated)]"
          :style="{ color: item.danger ? 'var(--status-error)' : 'var(--fg-primary)', fontFamily: 'var(--font-sans)' }"
          @click="handleItemClick(item)"
        >
          <AppIcon
            v-if="item.icon"
            :name="item.icon"
            size="xs"
            :style="{ color: item.danger ? 'var(--status-error)' : 'var(--brand-400)' }"
          />
          <span class="flex-1">{{ item.label }}</span>
          <span
            v-if="item.shortcut"
            class="font-mono text-[10px]"
            :style="{ color: 'var(--fg-tertiary)' }"
          >
            {{ item.shortcut }}
          </span>
        </button>
      </div>
    </Teleport>
  </div>
</template>

<script setup lang="ts">
export interface KebabMenuItem {
  label: string
  icon?: string
  shortcut?: string
  danger?: boolean
  onClick?: () => void
}

const props = withDefaults(
  defineProps<{
    items: KebabMenuItem[]
    size?: 24 | 28 | 32
    align?: "left" | "right"
  }>(),
  {
    size: 28,
    align: "right",
  },
)

const open = ref(false)
const pos = ref({ top: 0, left: 0 })
const btnRef = ref<HTMLElement | null>(null)
const menuRef = ref<HTMLElement | null>(null)

// Fecha ao clicar fora do menu (ignora o próprio botão trigger)
onClickOutside(menuRef, () => {
  if (open.value) open.value = false
}, { ignore: [btnRef] })

const sizeClass = computed(() => {
  if (props.size === 24) return "w-6 h-6"
  if (props.size === 32) return "w-8 h-8"
  return "w-7 h-7"
})

function updatePosition() {
  const r = btnRef.value?.getBoundingClientRect()
  if (!r) return
  const w = 200
  pos.value = {
    top: r.bottom + 6,
    left: props.align === "right" ? Math.max(8, r.right - w) : r.left,
  }
}

async function toggleOpen() {
  open.value = !open.value
  if (open.value) {
    await nextTick()
    updatePosition()
  }
}

function handleItemClick(item: KebabMenuItem) {
  item.onClick?.()
  open.value = false
}

defineExpose({ open, handleItemClick })
</script>
