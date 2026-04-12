<template>
  <nav class="flex items-center gap-1 p-1 rounded-[var(--radius-md)] bg-[var(--surface-elevated)]/60">
    <NuxtLink
      v-for="mod in modules"
      :key="mod.key"
      :to="mod.to"
      class="flex-1 flex items-center justify-center gap-1.5 px-2 py-1.5 rounded-[var(--radius-sm)] text-[11px] font-medium transition-colors"
      :class="[
        isActive(mod)
          ? 'bg-[var(--surface)] shadow-[var(--shadow-subtle)] text-[var(--text-primary)]'
          : 'text-[var(--text-tertiary)] hover:text-[var(--text-secondary)]',
      ]"
    >
      <AppIcon :name="mod.icon" size="xs" />
      <span>{{ mod.label }}</span>
    </NuxtLink>
  </nav>
</template>

<script setup lang="ts">
interface ModuleItem {
  key: string
  label: string
  icon: string
  to: string
  matches: string[]
}

const modules: ModuleItem[] = [
  {
    key: "chat",
    label: "Chat",
    icon: "chat-bubble-left-right",
    to: "/chat",
    matches: ["/chat"],
  },
  {
    key: "marketplace",
    label: "Market",
    icon: "squares-2x2",
    // `/deploy/` (com barra) matcha o wizard `/deploy/[slug]` mas NAO
    // matcha `/deployments` (senao `/deployments`.startsWith(`/deploy`)
    // seria true e as duas tabs ficariam ativas ao mesmo tempo).
    to: "/marketplace",
    matches: ["/marketplace", "/deploy/"],
  },
  {
    key: "deployments",
    label: "Deploys",
    icon: "rocket-launch",
    to: "/deployments",
    matches: ["/deployments"],
  },
  {
    key: "channels",
    label: "Canais",
    icon: "phone",
    to: "/channels",
    matches: ["/channels"],
  },
]

const route = useRoute()

function isActive(mod: ModuleItem): boolean {
  return mod.matches.some((m) => route.path.startsWith(m))
}
</script>
