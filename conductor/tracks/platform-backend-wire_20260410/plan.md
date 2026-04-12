# Implementation Plan: Platform — Backend Wire-up

**Track ID:** platform-backend-wire_20260410
**Spec:** [spec.md](./spec.md)
**Created:** 2026-04-10
**Status:** Complete

## Overview

4 fases sequenciais: models+migration+seed, routers+saga backend, refactor frontend stores, smoke test + pytest.

## Phase 1: Backend models + migration + seed

### Tasks

- [x] Task 1.1: `app/models/template.py` — Template model com slug unique, category, tags JSONB, env_schema JSONB, changelog JSONB
- [x] Task 1.2: `app/models/deployment.py` — Deployment + DeploymentStep + DeploymentLog models
- [x] Task 1.3: `app/models/__init__.py` — reexporta todos os models (inclusive novos + channels/user/audit)
- [x] Task 1.4: `app/database/migrations/versions/a7f3d9b12e45_add_templates_and_deployments.py` — Alembic migration com 4 tabelas + indices
- [x] Task 1.5: `app/database/seed.py` — `seed_templates()` idempotente com os 3 templates
- [x] Task 1.6: `app/main.py` — chama seed no lifespan se `AUTO_SEED=True`
- [x] Task 1.7: `app/core/config.py` — adiciona flag `AUTO_SEED`

### Verification

- [x] Models importaveis sem erro (verificado via `python -c "from app.main import app"`)
- [x] Ruff passa

## Phase 2: Schemas + Routers + Saga

### Tasks

- [x] Task 2.1: `app/schemas/template.py` — `TemplateResponse` com todos os campos
- [x] Task 2.2: `app/schemas/deployment.py` — `DeploymentConfigIn`, `DeploymentCreateRequest`, `DeploymentResponse` (com steps+logs), `DeploymentListItem`, `DeploymentEvent`
- [x] Task 2.3: `app/services/deployment_saga.py` — pub/sub in-memory via asyncio.Queue, `SAGA_BLUEPRINT` com 10 etapas, `STEP_LOGS` por etapa, `run_saga(id)` async que abre sua propria session e persiste steps/logs incrementalmente, suporta cancelamento via asyncio.Event
- [x] Task 2.4: `app/api/routes/templates.py` — `GET /templates` (filtro category+search), `GET /templates/{slug}`
- [x] Task 2.5: `app/api/routes/deployments.py` — `GET /deployments`, `GET /deployments/{id}`, `POST /deployments` (dispara saga via asyncio.create_task apos commit), `POST /deployments/{id}/cancel`, `GET /deployments/{id}/events` (SSE com heartbeat 30s)
- [x] Task 2.6: `app/main.py` — registra novos routers

### Verification

- [x] `from app.main import app` lista as 6 rotas novas
- [x] Ruff passa (0 errors)

## Phase 3: Frontend wiring

### Tasks

- [x] Task 3.1: `composables/useApiClient.ts` — exposto `baseURL` e removido re-export duplicado de useAuthStore
- [x] Task 3.2: `composables/useTemplatesApi.ts` — `list`/`getBySlug` com mapper DTO → Template (snake→camel)
- [x] Task 3.3: `composables/useDeploymentsApi.ts` — CRUD + `subscribeEvents` SSE via fetch+ReadableStream (Authorization header) com handlers onStep/onLog/onStatusChange/onComplete/onError
- [x] Task 3.4: `stores/templates.ts` — dual source (mocks em mockMode, API real fora) + `load()` async + fallback para mocks em caso de falha
- [x] Task 3.5: `stores/deployments.ts` — dual source, `createDeployment` async, `runSaga` subscreve SSE fora do mockMode, mantem `runSagaMock` para dev offline
- [x] Task 3.6: `stores/pipelines.ts` — dual source, `load()` via `/api/v1/pipelines` fora do mockMode
- [x] Task 3.7: Pages (`marketplace/index`, `marketplace/[slug]`, `deploy/[slug]`, `deployments/index`, `deployments/[id]`) chamam `store.load()` no setup; `deployments/[id]` subscreve SSE automaticamente se status=pending/running
- [x] Task 3.8: `components/organisms/DeployWizard.vue` — `createDeployment` agora e async
- [x] Task 3.9: `nuxt.config.ts` — comment atualizado sobre mockMode

### Verification

- [x] `nuxt prepare` sem errors (warning duplicated imports resolvido)
- [x] `bun run lint` = 0 errors

## Phase 4: Tests + smoke validacao

### Tasks

- [x] Task 4.1: `tests/unit/test_deployment_saga.py` — 5 testes (blueprint structure, step_logs coverage, pub/sub roundtrip, multi-subscriber broadcast, publish sem subs)
- [x] Task 4.2: `tests/unit/test_template_seed.py` — 7 testes parametrizados (3 templates com shape completo)
- [x] Task 4.3: `tests/unit/test_schemas.py` — 3 testes Pydantic (defaults, validacao, campos do response)
- [x] Task 4.4: Instalado `pytest-asyncio` no venv
- [x] Task 4.5: 18 testes passando
- [x] Task 4.6: Ruff + lint frontend verdes
- [x] Task 4.7: Fechar metadata + index + tracks.md

### Verification

- [x] `pytest tests/unit/` = 18 passed
- [x] `ruff check app/ tests/` = All checks passed
- [x] `bun run lint` = 0 errors
- [x] Track marcada como complete

## Final Verification

- [x] Acceptance criteria atendidos para backend wire-up de templates+deployments
- [x] SSE stream funcional com pub/sub in-memory
- [x] Dual-source stores (mock ou API real via flag)
- [x] Testes unitarios cobrem saga pub/sub e seed shape

## Follow-ups

- Wire real de `stores/threads.ts` para o backend chat existente fica para track futura (precisa de um pipeline registrado no DB antes)
- Persistir `pipeline_id` de verdade apos deploy bem-sucedido (hoje e None placeholder)
- Substituir asyncio.create_task por Celery quando houver job queue

---

_Generated by Conductor._
