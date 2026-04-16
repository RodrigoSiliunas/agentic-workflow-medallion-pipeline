# ADR 0002 — Saga pattern para one-click deploy

**Status**: accepted · **Data**: 2026-04-16 · **Track**: T4

## Contexto

O produto `agentic-workflow-medallion-pipeline` monta infra AWS + Databricks via backend Python. Cada deploy toca múltiplos sistemas externos (S3, IAM, Secrets, Unity Catalog, Workflows). Antes da T4 a saga estava meia-construída:

- Sem compensating actions — falha em step N deixava recursos órfãos dos steps 0..N-1 pagos em AWS/Databricks.
- `cleanup_shared_state` nunca chamado fora do happy-path — memory leak por deploy falhado.
- Pub/sub SSE in-memory — quebrava em qualquer setup multi-worker (uvicorn `--workers >1`, ECS N tasks).
- Steps registrados em dict hardcoded em `runner.py` — adicionar step novo = edit em 3 lugares.
- `emit_log` era closure com `noqa: B023` — misturava DB + lock + cancel + publish num fechamento difícil de testar.

## Decisão

Amadurecer a saga em 5 eixos coordenados (T4 fases 1–5), mantendo o protocol `SagaStepRunner` retrocompatível:

### 1. Compensating actions (Phase 1)

- `SagaStep` protocol mantém `execute` obrigatório; `compensate` é **opcional** (duck-typed via `hasattr` no runner).
- `SagaStepBase` oferece `compensate` default (no-op logado). Steps de criação real (S3, IAM, …) sobrescrevem.
- `RealSagaRunner` mantém `_completed_per_deployment: dict[str, list[tuple[step_id, ctx]]]`. Step só entra no histórico **após success** — falha em execute não entra.
- `run_compensation(deployment_id)` percorre reverse, loga warn em erros de compensate individuais mas **continua a cadeia** (não mascara o erro do step que falhou originalmente).

### 2. Cleanup unconditional (Phase 2)

- `deployment_saga.run_saga` chama `step_runner.cleanup_shared_state(dep_id)` em `finally` — cobre success, failure e cancel.
- Usa `getattr` pra tolerar runners que não expõem o método (MockSagaRunner).

### 3. Pub/sub backend pluggable (Phase 3)

- Novo módulo `app/services/pubsub_backend.py` com protocol `PubSubBackend` + implementações `InMemoryPubSub` e `RedisPubSub`.
- `get_pubsub()` escolhe backend na primeira chamada: Redis se `settings.REDIS_URL` reachable (ping), senão in-memory.
- Redactor de URL log-seguro (`redis://***@host`).
- `_publish` publica em **ambos** (backend + fallback in-memory) — garante que subscribe sync legacy (API `subscribe(deployment_id) -> asyncio.Queue`) continua funcionando.

### 4. Step registry (Phase 4)

- `@register_saga_step("<id>")` decorator popula `STEP_REGISTRY: dict[str, type[SagaStep]]`.
- `RealSagaRunner.__init__` instancia a partir do registry em vez do dict hardcoded.
- Adicionar step novo = escrever a classe + decorator + import em `steps/__init__.py`. Zero edit em `runner.py`.

### 5. LogEmitter extraction (Phase 5)

- Closure `emit_log` com `noqa: B023` substituído por classe `LogEmitter` em `app/services/log_emitter.py`.
- Deps injetadas: `db`, `deployment_id`, `cancel_event`, `publish`, `log_lock`.
- Callable-as-class — continua satisfazendo o contrato `EmitLogFn = Callable[[str, str, str | None], Awaitable[None]]`.
- Testável isolado (`test_log_emitter.py` com 5 testes usando AsyncMock).

## Trade-offs

- **Compensate é best-effort**: steps devem ser idempotentes e tolerar recursos já ausentes. Um compensate que raise não aborta a cadeia — prioriza limpar o que der.
- **In-memory fallback duplo**: `_publish` manda pra Redis E pra in-memory pra preservar API legacy. Custo: fanout local redundante (barato). Benefício: zero breaking change nos testes existentes.
- **Decorator side-effect em import**: registry é populado por efeito colateral. `steps/__init__.py` importa tudo pra garantir que um `RealSagaRunner()` veja os 10 steps. Perde um pouco de explicitude mas casa com o pattern do observer-framework.
- **Compensate não implementado em todos os steps**: s3, iam têm rollback real; catalog/secrets/workflow/observer ainda no no-op. Ficam como TODOs pra tracks dedicados. Runner tolera via `getattr`.

## Consequências

- Multi-worker uvicorn passa a funcionar (Redis habilitado quando disponível).
- Deploy falhado limpa recursos criados (pagos em AWS) sem ação manual.
- Adição de novo step (ex: `dashboards` futuro) = 1 arquivo + 1 import.
- `deployment_saga.py` diminui de 442 LOC pra ~400, com lógica de logs externalizada.

## Revisão

Reavaliar em 6 meses (~2026-10):
- Quantos compensate foram acionados em prod? Bugs de idempotência detectados?
- Redis pubsub escala? Considerar dedicated pubsub service (NATS/Kafka) se vier volume alto.
- Migrar saga state pra DB persistente (hoje memória) pra permitir retomar deploys pós-restart do worker.
