# Implementation Plan: Platform Frontend (Nuxt 4)

**Track ID:** platform-frontend_20260408
**Spec:** [spec.md](./spec.md)
**Created:** 2026-04-08
**Status:** [ ] Not Started

## Overview

Implementar frontend Nuxt 4 com Atomic Design: auth, sidebar Claude Projects, chat SSE, settings com credenciais e QR Code, gestao de usuarios.

## Phase 1: Auth + Layout Base

### Tasks

- [ ] Task 1.1: Pinia store auth (login, logout, refresh, role getters — padrao idlehub)
- [ ] Task 1.2: Composable useApiClient (token refresh, request queue, 401 handling)
- [ ] Task 1.3: Middleware auth.global.ts (redirect /login, guest routes)
- [ ] Task 1.3b: Middleware role.ts (protege /settings e /admin por role, nao apenas por componente)
- [ ] Task 1.4: Server route proxy: server/api/proxy/[...].ts (passthrough SSE para FastAPI backend)
- [ ] Task 1.5: Types: types/chat.ts, types/pipeline.ts, types/user.ts (derivados do OpenAPI do backend)
- [ ] Task 1.6: Layout auth.vue (login/register, clean layout)
- [ ] Task 1.7: Layout default.vue (sidebar + main area, 2 colunas)
- [ ] Task 1.8: Pages: login.vue, pagina principal redirect
- [ ] Task 1.9: Atoms: AppButton, AppInput, AppBadge, AppAvatar, AppSpinner

### Verification

- [ ] Login funciona, token armazenado, refresh automatico
- [ ] Middleware redireciona para /login se nao autenticado
- [ ] Layout 2 colunas renderiza

## Phase 2: Sidebar + Pipeline Navigation

### Tasks

- [ ] Task 2.1: Composable usePipelines (list, status polling 30s)
- [ ] Task 2.2: Composable useSidebar (expand/collapse, active pipeline/thread)
- [ ] Task 2.3: Composable useThreads (CRUD, list by pipeline)
- [ ] Task 2.4: Atom: ChannelIcon (web/whatsapp/discord/telegram icons)
- [ ] Task 2.5: Molecule: StatusBadge (SUCCESS/FAILED/RUNNING com cores)
- [ ] Task 2.6: Organism: SidebarNav (pipelines expandiveis, threads, + nova conversa)
- [ ] Task 2.7: Organism: ThreadItem (UUID, data, preview, canal de origem, delete)
- [ ] Task 2.8: Pages: chat/index.vue, chat/[pipelineId]/[threadId].vue

### Verification

- [ ] Sidebar mostra pipelines com status badge
- [ ] Clique expande threads do usuario
- [ ] Criar/deletar thread funciona
- [ ] Navegar entre threads muda o chat

## Phase 3: Chat Window + SSE Streaming

### Tasks

- [ ] Task 3.1: Composable useChat (SSE streaming, sendMessage com FormData, loadHistory)
- [ ] Task 3.2: Molecule: MessageBubble (user/assistant, Markdown render, timestamp, canal)
- [ ] Task 3.3: Molecule: ActionCard (PR criado, run disparado, query executada — clicavel)
- [ ] Task 3.4: Molecule: ConfirmDialog (confirmacao inline para acoes perigosas)
- [ ] Task 3.5: Organism: ChatWindow (MessageList + ChatInput)
- [ ] Task 3.6: Organism: ChatInput (Shift+Enter, drag & drop imagens/arquivos, send button)
- [ ] Task 3.7: StreamingMessage (conteudo em construcao com cursor piscante)
- [ ] Task 3.8: Composable useAttachments (upload FormData, preview, validacao tamanho, tipos permitidos)
- [ ] Task 3.9: Molecule: ChartCard (renderiza dados de generate_chart_data com VueChart.js)
- [ ] Task 3.10: Template: ChatLayout (sidebar + chat area)

### Verification

- [ ] Mensagem enviada, resposta streaming aparece em tempo real
- [ ] Markdown renderiza (headers, code blocks, tabelas)
- [ ] Action cards mostram PR link clicavel
- [ ] Imagens/arquivos podem ser anexados
- [ ] Historico carrega ao abrir thread existente

## Phase 4: Settings + Credential Management + QR Code

### Tasks

- [ ] Task 4.1: Composable useSettings (CRUD credenciais, test connection)
- [ ] Task 4.2: Pages: settings.vue com tabs (Geral, Credenciais, Canais, Usuarios)
- [ ] Task 4.3: Organism: CredentialsForm (Anthropic, Databricks, GitHub — input + testar)
- [ ] Task 4.4: Organism: ChannelsForm (Discord token, Telegram token, status de conexao)
- [ ] Task 4.5: Organism: QrCodePairing (botao Conectar → mostra QR → status atualizado)
- [ ] Task 4.6: Organism: UserTable (lista usuarios, criar, editar role, desativar)
- [ ] Task 4.7: Organism: ModelSelector (Sonnet/Opus, preferencia da empresa)
- [ ] Task 4.8: Organism: ChannelHealthStatus (status de cada canal: connected/disconnected/pairing)
- [ ] Task 4.9: Template: SettingsLayout (tabs + content area)
- [ ] Task 4.10: Role-based visibility: viewer nao ve /settings, editor ve parcial (enforced por middleware/role.ts)

### Verification

- [ ] Admin salva Anthropic key → "Testar" → feedback visual OK/erro
- [ ] QR Code WhatsApp aparece e atualiza em tempo real
- [ ] Admin cria usuario com role viewer
- [ ] Viewer nao consegue acessar /settings

## Phase 5: Polish + Tests

### Tasks

- [ ] Task 5.1: Dark/light mode (@nuxt/ui colorMode)
- [ ] Task 5.2: Responsive (mobile: sidebar collapsa)
- [ ] Task 5.3: Loading states em todas as paginas
- [ ] Task 5.4: Error boundaries (fallback UI para erros)
- [ ] Task 5.5: Testes Vitest: composables (useAuth, useChat mock), componentes (MessageBubble, StatusBadge)
- [ ] Task 5.6: SEO basico (title, meta)

### Verification

- [ ] Dark mode funciona
- [ ] Mobile usavel (sidebar colapsa)
- [ ] Testes passando

## Final Verification

- [ ] Login → sidebar → selecionar pipeline → chat funcional
- [ ] SSE streaming sem lag
- [ ] Settings: credenciais + QR Code + usuarios
- [ ] Cross-channel: conversa do WhatsApp aparece na sidebar web
- [ ] Atomic Design respeitado (atoms sem logica, organisms com composables)

---

_Generated by Conductor._
