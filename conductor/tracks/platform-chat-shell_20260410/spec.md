# Specification: Platform — Chat shell estilo Claude.ai

**Track ID:** platform-chat-shell_20260410
**Type:** Feature
**Created:** 2026-04-10
**Status:** Draft

## Summary

Implementar o shell pos-login da plataforma Namastex inspirado na interface do `claude.ai`: sidebar com threads agrupadas + lista de pipelines + chat principal vinculado ao workflow ativo. Tudo com mocks por enquanto (zero conexao com backend real). Atomic Design seguindo o `ATOMIC_DESIGN.md` e tokens visuais da Track A (`platform-design-namastex_20260410`).

## User Story

Como usuario da plataforma Namastex, quero entrar na app, ver minhas conversas anteriores na sidebar agrupadas por data (Today, Last 7 days, Older), selecionar um pipeline ativo, e conversar diretamente com o agente associado a esse workflow — exatamente como faria no claude.ai mas focado em pipelines de dados.

## Acceptance Criteria

### Layout

- [ ] Shell de 2 colunas: sidebar fixa esquerda (280px desktop) + main flex
- [ ] Sidebar contem (de cima para baixo):
  - Header com logo Namastex + nome do usuario logado
  - Botao "+ Nova conversa" em destaque
  - Secao "Threads" com agrupamento Today / Last 7 days / Older
  - Secao "Pipelines" com 1 item: medallion_pipeline_whatsapp + status badge
  - Botao "+ Deploy pipeline" (placeholder, abre modal "Em breve")
  - Footer com Settings + Logout
- [ ] Main content tem dois estados:
  - **Empty state**: quando nenhuma thread esta selecionada — heading "Comece uma conversa", subtitle, CTA, sugestoes de prompt
  - **Thread aberta**: header com nome do workflow + status badge + actions, lista de mensagens, input fixo no bottom

### Componentes (Atomic Design)

- [ ] `atoms/`:
  - `AppButton` (variantes solid/outline/ghost/danger, sizes sm/md/lg, loading)
  - `AppInput` (text + textarea, label, error, helper)
  - `AppBadge` (status colors)
  - `AppAvatar` (imagem ou inicial)
  - `AppIcon` (wrapper @nuxt/icon)
  - `AppKbd` (keyboard hints estilo `⌘K`, `↵`)

- [ ] `molecules/`:
  - `ThreadListItem` (titulo + preview + timestamp relativo + active state)
  - `MessageBubble` (variantes user/assistant)
  - `StatusBadge` (success/failed/running/idle com dot animado)
  - `EmptyState` (icon + heading + description + CTA opcional)
  - `PipelineCard` (nome + status badge + last run info)
  - `NewThreadButton` (CTA grande)

- [ ] `organisms/`:
  - `SidebarNav` (header user + new thread + thread list + pipelines + footer settings/logout)
  - `ThreadList` (agrupada por bucket de tempo)
  - `ChatWindow` (header + message list + input)
  - `MessageList` (scroll, agrupamento por dia)
  - `MessageInput` (textarea com submit, Shift+Enter, attach placeholder)
  - `WorkflowHeader` (nome workflow + status + dropdown actions)

- [ ] `templates/`:
  - `AppShell` (sidebar + main com slot)

### Pages

- [ ] `/` redireciona para `/login` (se nao autenticado) ou `/chat` (autenticado)
- [ ] `/chat` mostra empty state dentro do AppShell
- [ ] `/chat/[id]` mostra thread aberta dentro do AppShell
- [ ] `/chat/new` cria nova thread mock e redireciona para `/chat/[novoId]`
- [ ] `/login` permanece como esta (ja existe)

### Stores e Tipos

- [ ] Pinia store `threads.ts` com mock data e actions (create, list, get, addMessage)
- [ ] Pinia store `pipelines.ts` com 1 pipeline mockado (medallion_pipeline_whatsapp, status active)
- [ ] `types/chat.ts` com interfaces `Thread`, `Message`, `Pipeline`, `Workflow`

### Auth

- [ ] Middleware global `auth.ts` valida store auth — se nao tem user, redireciona para `/login`
- [ ] Store auth pode ser mock por enquanto (autoriza qualquer email/senha)

## Dependencies

- **platform-design-namastex_20260410** — tokens CSS e Geist devem estar configurados antes desta track

## Out of Scope

- Conexao real com backend FastAPI (mocks bastam)
- Streaming SSE real do LLM (simulacao com setTimeout)
- One-click deploy completo — so placeholder do botao
- Upload de arquivos / drag and drop
- Markdown rendering pesado (Shiki, KaTeX) — texto plain por enquanto
- Light mode polish
- Testes Vitest exaustivos — apenas smoke test em 1-2 atoms se sobrar tempo
- Omni / WhatsApp QR (track separada)

## Technical Notes

### Mock data approach

```ts
// stores/threads.ts
export const useThreadsStore = defineStore("threads", () => {
  const threads = ref<Thread[]>([
    {
      id: "t-001",
      title: "Por que o bronze falhou hoje?",
      preview: "O bronze_ingestion teve OOM no driver as 14h. O Observer ja...",
      createdAt: new Date(),
      messages: [
        { id: "m-1", role: "user", content: "Por que o bronze falhou hoje?", createdAt: new Date() },
        { id: "m-2", role: "assistant", content: "O bronze_ingestion teve OOM no driver...", createdAt: new Date() },
      ],
    },
    // ...mais threads mockados, pelo menos 1 por bucket (Today, Last 7 days, Older)
  ])
  // actions: create, list, get, addMessage
})
```

### Mock streaming

```ts
async function streamMockResponse(content: string, onChunk: (chunk: string) => void) {
  const tokens = content.split(" ")
  for (const token of tokens) {
    await new Promise((r) => setTimeout(r, 50))
    onChunk(token + " ")
  }
}
```

### Roteamento Nuxt 4

```
app/pages/
├── index.vue              → redirect /login ou /chat
├── login.vue              → ja existe
└── chat/
    ├── index.vue          → empty state
    ├── new.vue            → cria thread mock e push pra [id]
    └── [id].vue           → thread aberta
```

### Componentes @nuxt/ui usados como base

- `UButton` por baixo do `AppButton`
- `UInput`, `UTextarea` por baixo do `AppInput`
- `UBadge` por baixo do `AppBadge`
- `UAvatar` por baixo do `AppAvatar`
- `UIcon` por baixo do `AppIcon`
- `UKbd` por baixo do `AppKbd`

Os "App*" wrappers existem para garantir que todo o app use a mesma combinacao de variantes/cores Namastex e que a gente possa trocar o lib por baixo no futuro sem reescrever cada uso.

---

_Generated by Conductor._
