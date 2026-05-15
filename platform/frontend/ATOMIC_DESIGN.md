# Guia de Atomic Design — Flowertex Platform

## Hierarquia de Componentes

```
components/
├── atoms/          Elementos indivisíveis, sem lógica de negócio
├── molecules/      Combinação de atoms, estado local simples
├── organisms/      Seções completas, usam composables e stores
└── templates/      Layouts de página, combinam organisms
```

## Regras por Nível

### Atoms (`components/atoms/`)
- **Zero** dependência de lógica de negócio
- Apenas `defineProps()` + `defineEmits()`
- **Não** usam composables, stores, ou fetch
- Exemplos: Button, Input, Badge, Avatar, Spinner, Icon, Tooltip

```vue
<!-- atoms/AppButton.vue -->
<template>
  <UButton :variant="variant" :size="size" :loading="loading" @click="$emit('click')">
    <slot />
  </UButton>
</template>

<script setup lang="ts">
defineProps<{
  variant?: "solid" | "outline" | "ghost"
  size?: "sm" | "md" | "lg"
  loading?: boolean
}>()
defineEmits<{ click: [] }>()
</script>
```

### Molecules (`components/molecules/`)
- Combinam 2+ atoms
- Podem ter estado local (`ref`, `computed`)
- **Não** usam stores ou chamadas API
- Exemplos: SearchBar, FormField, StatusBadge, MessageBubble, ActionCard

```vue
<!-- molecules/StatusBadge.vue -->
<template>
  <div class="flex items-center gap-2">
    <AppBadge :color="color">{{ label }}</AppBadge>
    <span class="text-sm text-muted">{{ description }}</span>
  </div>
</template>

<script setup lang="ts">
const props = defineProps<{
  status: "success" | "failed" | "running" | "idle"
}>()

const color = computed(() => ({
  success: "green", failed: "red", running: "yellow", idle: "gray",
}[props.status]))

const label = computed(() => ({
  success: "OK", failed: "Falhou", running: "Rodando", idle: "Parado",
}[props.status]))
</script>
```

### Organisms (`components/organisms/`)
- Combinam molecules e atoms
- **Podem** usar composables (`useChat`, `usePipelines`, etc.)
- **Podem** usar stores (Pinia)
- **Podem** fazer fetch de dados
- Exemplos: ChatWindow, Sidebar, ThreadList, PipelineCard, MessageList

```vue
<!-- organisms/ChatWindow.vue -->
<template>
  <div class="flex flex-col h-full">
    <MessageList :messages="messages" />
    <ChatInput @send="sendMessage" :disabled="isStreaming" />
  </div>
</template>

<script setup lang="ts">
const props = defineProps<{ threadId: string }>()
const { messages, isStreaming, sendMessage } = useChat(toRef(props, "threadId"))
</script>
```

### Templates (`components/templates/`)
- Definem o layout da pagina
- Combinam organisms
- **Não** fazem fetch — recebem dados via props ou slots
- Exemplos: ChatLayout, AuthLayout, AdminLayout

```vue
<!-- templates/ChatLayout.vue -->
<template>
  <div class="flex h-screen">
    <Sidebar class="w-72 border-r" />
    <main class="flex-1">
      <slot />
    </main>
  </div>
</template>
```

## Nomenclatura

| Nivel | Prefixo | Exemplo |
|-------|---------|---------|
| Atom | `App` ou dominio | `AppButton`, `AppInput`, `AppBadge` |
| Molecule | Descritivo | `SearchBar`, `MessageBubble`, `StatusBadge` |
| Organism | Feature + Area | `ChatWindow`, `SidebarNav`, `ThreadList` |
| Template | Area + Layout | `ChatLayout`, `AuthLayout` |

## Quando Criar Novo Componente

1. **Vai ser reutilizado?** → Atom ou Molecule
2. **Tem lógica de negócio?** → Organism
3. **Define layout de pagina?** → Template
4. **So aparece em uma pagina?** → Pode ficar na pagina mesmo (nao precisa de componente)

## Composables vs Components

- **Composable**: lógica reutilizavel SEM template (useChat, useAuth, useApiClient)
- **Component**: template reutilizavel COM ou SEM lógica

Se so tem lógica → composable.
Se so tem template → atom/molecule.
Se tem ambos → organism.
