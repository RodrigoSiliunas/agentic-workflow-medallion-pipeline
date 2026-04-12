# Track: Platform — Backend Wire-up

**ID:** platform-backend-wire_20260410
**Status:** Complete

## Documents

- [Specification](./spec.md)
- [Implementation Plan](./plan.md)

## Progress

- Phases: 4/4 complete
- Tasks: 26/26 complete

## Validation

- `pytest tests/unit/` = **18 passed**
- `ruff check app/ tests/` = **All checks passed**
- `nuxt prepare` sem errors (warning duplicated imports corrigido)
- `bun run lint` = **0 errors** (1 warning aceitavel: v-html em MessageBubble)

## Entrega backend

- 4 tabelas novas: `templates`, `deployments`, `deployment_steps`, `deployment_logs`
- Alembic migration `a7f3d9b12e45` revise de `e2082b4df8fe`
- Seed idempotente de 3 templates (chamado no lifespan)
- 6 rotas novas: `/api/v1/templates` (list+slug), `/api/v1/deployments` (list+get+create+cancel+events SSE)
- Saga mock com pub/sub in-memory via asyncio.Queue, 10 etapas com logs incrementais, background via `asyncio.create_task`
- Heartbeat SSE de 30s para manter conexao viva

## Entrega frontend

- `useApiClient` exposto com baseURL
- `useTemplatesApi` e `useDeploymentsApi` com mappers DTO → types
- Stores dual-source (`mockMode` ativo por default; flip `NUXT_PUBLIC_MOCK_MODE=false` pra conectar no backend real)
- Pages fazem `store.load()` no setup
- `/deployments/[id]` auto-subscribe no SSE quando status=pending/running

## Follow-ups identificados

- Wire de `stores/threads.ts` para backend chat (precisa de pipeline registrado no DB)
- Persistir `pipeline_id` real apos saga success
- Migrar `asyncio.create_task` para Celery quando tiver queue real

## Quick Links

- [Back to Tracks](../../tracks.md)
- [Product Context](../../product.md)
