# Specification: Platform — Backend Wire-up

**Track ID:** platform-backend-wire_20260410
**Type:** Feature
**Created:** 2026-04-10
**Status:** Draft

## Summary

Desmockar o frontend Nuxt conectando-o ao backend FastAPI real. O backend ja possui auth/JWT/RBAC, models de chat/pipeline, SSE streaming do LLM e routers de auth/chat/pipelines. Esta track adiciona os recursos que faltam para o frontend rodar end-to-end: **Templates** (marketplace) e **Deployments** (one-click deploy com saga assincrona via SSE). Em seguida, refatora os Pinia stores para consumir a API real quando `mockMode=false`.

## User Story

Como Rodrigo (admin), quero que minha interface Namastex consuma dados reais do backend: quando eu faco login, o JWT do FastAPI e usado; quando eu abro uma thread, as mensagens vem do Postgres; quando eu abro o marketplace, os templates vem de `/api/v1/templates`; e quando eu disparo um deploy, a saga roda no backend e os logs chegam via SSE. Quero poder alternar para `mockMode=true` quando estou offline.

## Acceptance Criteria

### Backend — Models + Migration

- [ ] SQLAlchemy model `Template` com campos: slug (PK secundario), name, tagline, description, category, tags (JSONB), icon, icon_bg, version, author, deploy_count, duration_estimate, architecture_bullets (JSONB), env_schema (JSONB), changelog (JSONB), published
- [ ] SQLAlchemy model `Deployment` com campos: id (UUID), company_id (FK), user_id (FK), template_slug, template_name, config (JSONB), status, created_at, started_at, finished_at, duration_ms, pipeline_id
- [ ] SQLAlchemy model `DeploymentStep` com: deployment_id (FK), step_id, name, description, status, started_at, finished_at, duration_ms, error_message, order_index
- [ ] SQLAlchemy model `DeploymentLog` com: deployment_id (FK), timestamp, level, message, step_id
- [ ] Alembic migration `0005_templates_and_deployments` criando as 4 tabelas
- [ ] Seed script populando 3 templates fixos (os mesmos do frontend mock)

### Backend — Schemas Pydantic

- [ ] `TemplateResponse` (full serialization) + `TemplateListResponse` (summary)
- [ ] `DeploymentCreateRequest` (template_slug, config)
- [ ] `DeploymentResponse` (com steps + logs aninhados)
- [ ] `DeploymentListResponse` (summary sem logs pesados)
- [ ] `DeploymentEventSchema` (payload do SSE stream)

### Backend — Routers

- [ ] `GET /api/v1/templates` — lista templates (filtros ?category, ?search)
- [ ] `GET /api/v1/templates/{slug}` — detalhe de um template
- [ ] `GET /api/v1/deployments` — lista deployments da empresa
- [ ] `GET /api/v1/deployments/{id}` — detalhe
- [ ] `POST /api/v1/deployments` — cria deployment, dispara saga em background via asyncio.create_task, retorna deployment com id
- [ ] `GET /api/v1/deployments/{id}/events` — SSE stream com steps/logs ao vivo (in-memory queue por deployment_id)
- [ ] `POST /api/v1/deployments/{id}/cancel` — marca como cancelled

### Backend — Saga Runner

- [ ] `app/services/deployment_saga.py` com `DeploymentSaga` class
- [ ] `SAGA_STEPS` lista das 10 etapas blueprint
- [ ] `run(deployment_id)` async que: 1) atualiza status running, 2) itera steps, 3) emite eventos para queue in-memory, 4) persiste steps e logs no DB, 5) ao final marca status success
- [ ] Todas as etapas sao mockadas com `asyncio.sleep(2 + random)` + logs pre-definidos (mesmos do frontend)
- [ ] Suporta cancelamento via asyncio.Event

### Backend — Seed

- [ ] `app/database/seed.py` com `seed_templates()` que insere os 3 templates se nao existirem
- [ ] Chamado no lifespan startup se `settings.AUTO_SEED=True`

### Frontend — API Client wrapper

- [ ] `composables/useTemplatesApi.ts` — GET list/slug
- [ ] `composables/useDeploymentsApi.ts` — CRUD + SSE subscribe
- [ ] `composables/useSseClient.ts` — helper para consumir SSE
- [ ] Atualizar `useApiClient.ts` se necessario (ja existe, verificar)

### Frontend — Stores refactor

- [ ] `stores/templates.ts` — quando `mockMode=false`, faz fetch via useTemplatesApi. Mantem os mocks como fallback offline
- [ ] `stores/deployments.ts` — quando `mockMode=false`, cria via POST, conecta ao SSE, atualiza estado reativo. Mantem runSaga mock para offline
- [ ] `stores/threads.ts` — quando `mockMode=false`, usa os endpoints de chat reais ja existentes
- [ ] `stores/pipelines.ts` — quando `mockMode=false`, usa `GET /api/v1/pipelines`
- [ ] `stores/auth.ts` — ja tem suporte a mock mode, verificar que login real funciona

### Frontend — Config

- [ ] Default `mockMode=false` se `NUXT_PUBLIC_MOCK_MODE` nao estiver definido e o backend estiver reachable
- [ ] Comment no `.env.example` explicando como ativar mock mode

### Tests

- [ ] `tests/api/test_templates.py` — 2 tests: list + get by slug
- [ ] `tests/api/test_deployments.py` — 3 tests: create, list, get
- [ ] `tests/services/test_deployment_saga.py` — 1 test: saga run completes com mock fast

## Dependencies

- **platform-oneclick-deploy_20260410** — frontend com stores + pages ja existentes (COMPLETE)
- Backend ja tem auth/DB/LLM funcionais

## Out of Scope

- Conexao real com Terraform/Databricks SDK (saga continua mockada no backend tambem)
- Celery/Redis para job queue (usamos asyncio.create_task nesta fase)
- Persistencia de logs em tabela separada com TTL/rotation
- Autorizacao fine-grained por template (todos veem todos os templates)
- Multi-tenant marketplace (templates sao globais por enquanto)
- Webhook de notificacao quando saga termina
- Retry logic nas etapas da saga

## Technical Notes

### In-memory event bus para SSE

```python
# services/deployment_saga.py
from asyncio import Queue
from collections import defaultdict

_queues: dict[str, list[Queue]] = defaultdict(list)

def subscribe(deployment_id: str) -> Queue:
    q = Queue()
    _queues[deployment_id].append(q)
    return q

async def publish(deployment_id: str, event: dict):
    for q in _queues.get(deployment_id, []):
        await q.put(event)
```

SSE route consome a queue e yieldsa eventos. Ao fechar, remove a queue do bus.

### Mock mode flag — estrategia

`runtimeConfig.public.mockMode` ja existe. A mudanca e:
- Default = `false` (producao vai wire real)
- Se quiser mockar para dev offline, setar `NUXT_PUBLIC_MOCK_MODE=true`
- Cada store checa `config.public.mockMode` no primeiro load e escolhe source

### Seed templates

Os 3 templates (pipeline-seguradora-whatsapp, pipeline-crm-sap, pipeline-ecommerce-hotmart) sao copiados do arquivo `stores/templates.ts` para um `seed.py` no backend. Para evitar divergencia, no futuro podemos gerar o TS a partir de um schema JSON, mas por ora duplicacao e aceitavel.

---

_Generated by Conductor._
