"""DeploymentSaga — runner mock do one-click deploy.

Cada etapa dorme 250-500ms por log emitido e persiste estado reativo
no DB. Eventos sao republicados em queues in-memory para consumo
via SSE por clientes conectados em `/deployments/{id}/events`.
"""

import asyncio
import uuid
from datetime import UTC, datetime
from typing import Any

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.session import AsyncSessionLocal
from app.models.deployment import Deployment, DeploymentLog, DeploymentStep
from app.models.pipeline import Pipeline
from app.services.log_emitter import LogEmitter
from app.services.pubsub_backend import InMemoryPubSub, get_pubsub
from app.services.real_saga.base import DeploymentCredentials
from app.services.saga_runners import MOCK_STEP_LOGS, SagaStepRunner, get_runner

logger = structlog.get_logger()


SAGA_BLUEPRINT: list[dict[str, str]] = [
    {
        "id": "validate",
        "name": "Validate credentials",
        "description": "Checa AWS STS, Databricks token, GitHub PAT e Anthropic key",
    },
    {
        "id": "s3",
        "name": "Create AWS S3 buckets",
        "description": "Datalake bucket + workspace root bucket com policy Databricks",
    },
    {
        "id": "network",
        "name": "Provision AWS network (VPC + NAT)",
        "description": (
            "VPC + 2 private subnets + NAT Gateway + SG self-ref + "
            "Databricks network config"
        ),
    },
    {
        "id": "workspace_credential",
        "name": "Create cross-account IAM role",
        "description": "Role pra Databricks lancar EC2 + Account API credentials registration",
    },
    {
        "id": "storage_configuration",
        "name": "Register storage configuration",
        "description": "POST Account API vinculando root bucket ao workspace setup",
    },
    {
        "id": "workspace_provision",
        "name": "Provision Databricks workspace",
        "description": "POST workspace + polling RUNNING + admin SCIM + PAT generation",
    },
    {
        "id": "metastore_assign",
        "name": "Attach Unity Catalog metastore",
        "description": "PUT workspace -> metastore (regional) + default catalog",
    },
    {
        "id": "iam",
        "name": "Provision IAM role for Unity Catalog",
        "description": "Role + policy de acesso ao bucket + trust relationship",
    },
    {
        "id": "secrets",
        "name": "Create Databricks secrets scope",
        "description": "Scope medallion-pipeline com credenciais AWS + Anthropic + GitHub",
    },
    {
        "id": "catalog",
        "name": "Setup Unity Catalog",
        "description": "Catalog + schemas bronze/silver/gold + grants",
    },
    {
        "id": "cluster_provision",
        "name": "Provision Databricks cluster",
        "description": "Cluster ETL m5d.large com instance profile + libs",
    },
    {
        "id": "upload",
        "name": "Upload pipeline notebooks",
        "description": "Sync do repositorio para /Workspace/Repos/{company}",
    },
    {
        "id": "observer",
        "name": "Deploy Observer Agent",
        "description": "Registra workflow do Observer no mesmo workspace",
    },
    {
        "id": "workflow",
        "name": "Create Databricks workflow",
        "description": "Job com 8 tasks (7 ETL + 1 Observer sentinel)",
    },
    {
        "id": "trigger",
        "name": "Trigger first run",
        "description": "Run inicial para validar o pipeline end-to-end",
    },
    {
        "id": "register",
        "name": "Register in Flowertex platform",
        "description": "Adiciona o pipeline ao seu dashboard com chat integrado",
    },
]


# Logs de exemplo por step sao mantidos pelo runner. Re-export para
# compat com testes que ainda importam `STEP_LOGS` daqui.
STEP_LOGS = MOCK_STEP_LOGS


# Cancellation events por deployment (sempre in-memory local ao worker —
# cancel_event so faz sentido no worker que iniciou a saga).
_cancellations: dict[str, asyncio.Event] = {}

# Fallback in-memory compat com tests sync que chamam subscribe/unsubscribe
# diretamente (sem async). get_pubsub() pode retornar Redis em producao,
# mas os tests antigos usam sync API. Mantemos esse dict por compat.
_fallback_inmem = InMemoryPubSub()


def subscribe(deployment_id: str) -> asyncio.Queue[dict[str, Any]]:
    """API sync legacy — cria queue no backend in-memory local.

    Para SSE moderno use `subscribe_async(deployment_id)` (async gen)
    que respeita o backend selecionado (Redis ou in-memory).
    """
    return _fallback_inmem.register(deployment_id)


def unsubscribe(deployment_id: str, queue: asyncio.Queue[dict[str, Any]]) -> None:
    """Remove queue do fallback in-memory sincronamente.

    Operação é O(n) num list — sem I/O. Manter sync evita race entre
    `unsubscribe()` e `_publish()` subsequente no mesmo event loop.
    """
    subs = _fallback_inmem._subscribers.get(deployment_id, [])
    if queue in subs:
        subs.remove(queue)
    if not subs:
        _fallback_inmem._subscribers.pop(deployment_id, None)


async def subscribe_async(deployment_id: str):
    """API async moderna — usa o backend pub/sub configurado (Redis ou in-mem)."""
    backend = await get_pubsub()
    async for event in backend.subscribe(deployment_id):
        yield event


async def _publish(deployment_id: str, event: dict[str, Any]) -> None:
    """Publica em ambos: backend pub/sub configurado + fallback in-memory.

    O fallback in-memory garante que testes sync (e a API legacy
    `subscribe()`) continuam funcionando. Em producao com Redis, ambos
    recebem (fanout local redundante sem custo relevante).
    """
    backend = await get_pubsub()
    try:
        await backend.publish(deployment_id, event)
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "pubsub backend publish raised",
            deployment_id=deployment_id,
            error=str(exc),
        )
    await _fallback_inmem.publish(deployment_id, event)


def request_cancel(deployment_id: str) -> None:
    """Sinaliza cancelamento do saga runner."""
    event = _cancellations.get(deployment_id)
    if event:
        event.set()


async def run_saga(
    deployment_id: uuid.UUID,
    runner: SagaStepRunner | None = None,
    credentials: DeploymentCredentials | None = None,
) -> None:
    """Executa a saga para o deployment dado.

    O runner concreto e plugavel via `settings.SAGA_RUNNER` (default: mock).
    Ver `app/services/saga_runners.py` pra detalhes.

    Cria uma nova session ao DB (nao reusa a session do request HTTP que
    ja foi encerrada). Atualiza status, steps e logs incrementalmente.
    Publica eventos em memoria para consumidores SSE conectados.

    `credentials` deve ser resolvido pelo caller (POST /deployments) como
    override > company_credentials, e vive apenas na memoria durante o
    tempo de vida do background task. O MockRunner ignora; o RealRunner
    usa pra autenticar em AWS/Databricks/GitHub.
    """
    dep_id_str = str(deployment_id)
    cancel_event = asyncio.Event()
    _cancellations[dep_id_str] = cancel_event

    step_runner: SagaStepRunner = runner or get_runner()

    async with AsyncSessionLocal() as db:
        try:
            deployment = await _load_deployment(db, deployment_id)
            if not deployment:
                logger.error("deployment not found for saga", deployment_id=dep_id_str)
                return

            await _initialize_steps(db, deployment_id)
            deployment.status = "running"
            deployment.started_at = datetime.now(UTC)
            await db.commit()
            await _publish(
                dep_id_str,
                {
                    "type": "status_change",
                    "deployment_id": dep_id_str,
                    "data": {"status": "running"},
                },
            )

            start_ms = _now_ms()

            for idx, blueprint in enumerate(SAGA_BLUEPRINT):
                if cancel_event.is_set():
                    await _mark_cancelled(db, deployment)
                    return

                step = await _update_step(
                    db,
                    deployment_id,
                    blueprint["id"],
                    status="running",
                    started_at=datetime.now(UTC),
                )
                await _publish(
                    dep_id_str,
                    {
                        "type": "step_update",
                        "deployment_id": dep_id_str,
                        "data": {
                            "step_id": blueprint["id"],
                            "status": "running",
                            "order_index": idx,
                        },
                    },
                )

                step_start_ms = _now_ms()
                log_lock = asyncio.Lock()

                # T4 Phase 5: LogEmitter substitui o closure com noqa: B023.
                # Deps explícitas, testável isolado, mesma semantica de
                # batching (flush por log, commit no boundary do step).
                emit_log = LogEmitter(
                    db=db,
                    deployment_id=deployment_id,
                    cancel_event=cancel_event,
                    publish=_publish,
                    log_lock=log_lock,
                )

                try:
                    await step_runner.execute_step(
                        deployment=deployment,
                        step_id=blueprint["id"],
                        step_name=blueprint["name"],
                        emit_log=emit_log,
                        credentials=credentials,
                    )
                except Exception as exc:
                    # Captura QUALQUER exception do step (nao so NotImplementedError).
                    # Marca o step individual como failed com error message truncada,
                    # loga a exception completa no server, e re-raise pro handler
                    # outer que marca o deployment como failed.
                    step.status = "failed"
                    step.finished_at = datetime.now(UTC)
                    step.duration_ms = _now_ms() - step_start_ms
                    step.error_message = f"{type(exc).__name__}: {exc}"[:500]
                    await db.commit()
                    raise

                if cancel_event.is_set():
                    await _mark_cancelled(db, deployment)
                    return

                step.status = "success"
                step.finished_at = datetime.now(UTC)
                step.duration_ms = _now_ms() - step_start_ms
                await db.commit()
                await _publish(
                    dep_id_str,
                    {
                        "type": "step_update",
                        "deployment_id": dep_id_str,
                        "data": {
                            "step_id": blueprint["id"],
                            "status": "success",
                            "duration_ms": step.duration_ms,
                        },
                    },
                )

            deployment.status = "success"
            deployment.finished_at = datetime.now(UTC)
            deployment.duration_ms = _now_ms() - start_ms

            # Cria o Pipeline real na tabela `pipelines` — assim o chat passa
            # a listar esse workflow e o usuario pode conversar com ele.
            # Tenta ler o workflow_job_id do shared state do runner
            # (so funciona com RealSagaRunner — MockRunner nao tem shared state).
            workflow_job_id = None
            if hasattr(step_runner, "_shared_per_deployment"):
                shared = step_runner._shared_per_deployment.get(dep_id_str)
                if shared is not None:
                    workflow_job_id = getattr(shared, "workflow_job_id", None)

            pipeline = Pipeline(
                company_id=deployment.company_id,
                name=deployment.name,
                description=f"Deploy de {deployment.template_name}",
                databricks_job_id=workflow_job_id,
                config={
                    "template_slug": deployment.template_slug,
                    "deployment_id": str(deployment.id),
                    "environment": deployment.environment,
                },
            )
            db.add(pipeline)
            await db.flush()
            deployment.pipeline_id = pipeline.id
            await db.commit()

            completion_log = DeploymentLog(
                deployment_id=deployment_id,
                level="success",
                message=f"Deployment successful in {deployment.duration_ms // 1000}s",
            )
            db.add(completion_log)
            await db.commit()

            await _publish(
                dep_id_str,
                {
                    "type": "complete",
                    "deployment_id": dep_id_str,
                    "data": {"status": "success", "duration_ms": deployment.duration_ms},
                },
            )
        except asyncio.CancelledError:
            await _mark_cancelled(db, deployment)
            # Melhor effort compensate ao cancelar tambem — deixa recursos
            # criados pra tras seria cost leak.
            await _run_compensation_safe(step_runner, dep_id_str)
            raise
        except Exception as exc:
            logger.exception("saga run failed", deployment_id=dep_id_str)
            # T4: roda compensate dos steps que ja completaram com sucesso
            # ANTES de marcar o deployment como failed — garante que
            # recursos orfaos de S3/IAM/Secret Scope/Catalog sejam
            # limpos na mesma request. Erros dentro de compensate nao
            # abortam o rollback (logados, continuam).
            await _run_compensation_safe(step_runner, dep_id_str)

            try:
                deployment = await _load_deployment(db, deployment_id)
                if deployment:
                    deployment.status = "failed"
                    deployment.finished_at = datetime.now(UTC)
                    await db.commit()
                # Mensagem generica pro SSE — detalhes ficam so no server log
                # (logger.exception acima). Evita vazar infra details, ARNs,
                # ou fragmentos de credenciais em exceptions de boto3/databricks-sdk.
                safe_msg = (
                    f"Deployment falhou no step em execucao. "
                    f"Tipo: {type(exc).__name__}. Verifique os logs do servidor."
                )
                await _publish(
                    dep_id_str,
                    {
                        "type": "error",
                        "deployment_id": dep_id_str,
                        "data": {"message": safe_msg},
                    },
                )
            except Exception:
                pass
        finally:
            # T4: cleanup unconditional — evita memory leak de deploys
            # parciais. Chamamos `cleanup_shared_state` se o runner expoe
            # o metodo (RealSagaRunner sim; MockSagaRunner nao tem estado
            # compartilhado pra liberar).
            cleanup = getattr(step_runner, "cleanup_shared_state", None)
            if callable(cleanup):
                try:
                    cleanup(dep_id_str)
                except Exception:  # noqa: BLE001
                    logger.warning(
                        "cleanup_shared_state raised",
                        deployment_id=dep_id_str,
                    )
            _cancellations.pop(dep_id_str, None)


async def _run_compensation_safe(step_runner: SagaStepRunner, dep_id_str: str) -> None:
    """Chama `step_runner.run_compensation` quando disponivel, tolerando erro.

    Runners mock nao tem rollback — metodo ausente = no-op. Exceptions
    durante compensate sao logadas mas nao propagadas, pra nao mascarar
    a exception original da saga.
    """
    runner_compensate = getattr(step_runner, "run_compensation", None)
    if not callable(runner_compensate):
        return
    try:
        await runner_compensate(dep_id_str)
    except Exception:  # noqa: BLE001
        logger.exception(
            "compensation chain raised", deployment_id=dep_id_str
        )


async def _load_deployment(db: AsyncSession, deployment_id: uuid.UUID) -> Deployment | None:
    result = await db.execute(select(Deployment).where(Deployment.id == deployment_id))
    return result.scalar_one_or_none()


async def _initialize_steps(db: AsyncSession, deployment_id: uuid.UUID) -> None:
    """Cria registros DeploymentStep para o blueprint inteiro (status pending)."""
    existing = await db.execute(
        select(DeploymentStep).where(DeploymentStep.deployment_id == deployment_id)
    )
    if existing.scalars().first():
        return
    for idx, blueprint in enumerate(SAGA_BLUEPRINT):
        db.add(
            DeploymentStep(
                deployment_id=deployment_id,
                step_id=blueprint["id"],
                name=blueprint["name"],
                description=blueprint["description"],
                status="pending",
                order_index=idx,
            )
        )
    await db.commit()


async def _update_step(
    db: AsyncSession,
    deployment_id: uuid.UUID,
    step_id: str,
    **updates: Any,
) -> DeploymentStep:
    result = await db.execute(
        select(DeploymentStep).where(
            DeploymentStep.deployment_id == deployment_id,
            DeploymentStep.step_id == step_id,
        )
    )
    step = result.scalar_one()
    for key, value in updates.items():
        setattr(step, key, value)
    await db.commit()
    return step


async def _mark_cancelled(db: AsyncSession, deployment: Deployment | None) -> None:
    if not deployment:
        return
    deployment.status = "cancelled"
    deployment.finished_at = datetime.now(UTC)
    await db.commit()
    dep_id_str = str(deployment.id)
    await _publish(
        dep_id_str,
        {
            "type": "status_change",
            "deployment_id": dep_id_str,
            "data": {"status": "cancelled"},
        },
    )


def _now_ms() -> int:
    return int(datetime.now(UTC).timestamp() * 1000)
