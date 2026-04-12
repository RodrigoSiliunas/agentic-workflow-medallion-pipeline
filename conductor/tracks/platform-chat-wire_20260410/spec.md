# Specification: Platform — Chat Wire-up to Backend Real

**Track ID:** platform-chat-wire_20260410
**Status:** Complete
**Created:** 2026-04-10

## Summary

Desmockar o chat do frontend conectando-o aos endpoints ja existentes no backend (`/api/v1/chat/threads`, `/api/v1/chat/message` com SSE). Resolve o bootstrap problem criando um pipeline default quando a company e registrada.

## Entrega

### Backend

- `register-company` cria automaticamente um pipeline `"Meu primeiro pipeline"` pra nova empresa — desbloqueia o primeiro login
- Schemas `PipelineResponse`, `ThreadResponse`, `MessageResponse` migrados para `uuid.UUID` + `datetime` (Pydantic v2 serializa corretamente no JSON — bug pre-existente)

### Frontend

- `useChatApi.ts` composable com `listThreads`, `createThread`, `deleteThread`, `getMessages`, `sendMessageStream` (SSE via fetch+ReadableStream com Authorization header)
- `stores/threads.ts` dual-source: mocks em mockMode, API real fora
  - `loadForPipeline(id)` popula threads do backend
  - `loadMessages(id)` hidrata mensagens de um thread
  - `create()` agora async — chama POST ou cria local dependendo do mode
  - `streamAssistantReply()` usa SSE real fora do mockMode
  - `remove()` async — chama DELETE no backend
- `pages/chat/[id].vue` carrega threads + mensagens no setup via SSR
- `SidebarNav` watch pipelineId changes pra recarregar threads automaticamente
- Call sites (`SidebarNav.onNewThread`, `chat/index.startWith`) migrados pra await create

## Smoke E2E validado

```
Register → default pipeline ✓
POST /chat/threads → thread criada ✓
GET /chat/threads?pipeline_id=... → lista volta ✓
GET /chat/threads/{id}/messages → array vazio (esperado) ✓
```

## Out of scope

- SSE do LLM Orchestrator precisa de `ANTHROPIC_API_KEY` configurada — nao testado end-to-end com streaming real
- Titulo automatico do thread apos primeira msg (backend ja tem, funciona)
