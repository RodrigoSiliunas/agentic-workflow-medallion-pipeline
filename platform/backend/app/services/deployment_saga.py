"""DeploymentSaga — runner mock do one-click deploy.

Cada etapa dorme 250-500ms por log emitido e persiste estado reativo
no DB. Eventos sao republicados em queues in-memory para consumo
via SSE por clientes conectados em `/deployments/{id}/events`.
"""

import asyncio
import uuid
from collections import defaultdict
from datetime import UTC, datetime
from typing import Any

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.session import AsyncSessionLocal
from app.models.deployment import Deployment, DeploymentLog, DeploymentStep
from app.models.pipeline import Pipeline
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
        "name": "Create AWS S3 bucket",
        "description": "terraform apply no modulo 02-datalake com tags multi-tenant",
    },
    {
        "id": "iam",
        "name": "Provision IAM role for Databricks",
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
        "name": "Register in Safatechx platform",
        "description": "Adiciona o pipeline ao seu dashboard com chat integrado",
    },
]


# Logs de exemplo por step sao mantidos pelo runner. Re-export para
# compat com testes que ainda importam `STEP_LOGS` daqui.
STEP_LOGS = MOCK_STEP_LOGS


# In-memory pub/sub — um dict mapeando deployment_id -> lista de asyncio.Queue
_subscribers: dict[str, list[asyncio.Queue[dict[str, Any]]]] = defaultdict(list)
# Cancellation events por deployment
_cancellations: dict[str, asyncio.Event] = {}


def subscribe(deployment_id: str) -> asyncio.Queue[dict[str, Any]]:
    """Cria uma queue para consumir eventos desse deployment."""
    queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue(maxsize=1000)
    _subscribers[deployment_id].append(queue)
    return queue


def unsubscribe(deployment_id: str, queue: asyncio.Queue[dict[str, Any]]) -> None:
    if queue in _subscribers.get(deployment_id, []):
        _subscribers[deployment_id].remove(queue)
    if not _subscribers[deployment_id]:
        _subscribers.pop(deployment_id, None)


async def _publish(deployment_id: str, event: dict[str, Any]) -> None:
    """Publica um evento em todas as queues desse deployment (non-blocking).

    Para eventos terminais (complete, error, status_change terminal), garante
    entrega mesmo sob backpressure — dropa o evento mais antigo se a queue
    estiver cheia, pra abrir espaco pro terminal event.
    """
    is_terminal = event.get("type") in ("complete", "error") or (
        event.get("type") == "status_change"
        and event.get("data", {}).get("status") in ("success", "failed", "cancelled")
    )
    for queue in list(_subscribers.get(deployment_id, [])):
        try:
            queue.put_nowait(event)
        except asyncio.QueueFull:
            if is_terminal:
                # Forca entrega: dropa o mais antigo pra abrir espaco
                try:
                    queue.get_nowait()
                    queue.put_nowait(event)
                except (asyncio.QueueEmpty, asyncio.QueueFull):
                    logger.warning(
                        "sse queue full, could not deliver terminal event",
                        deployment_id=deployment_id,
                    )
            else:
                logger.warning(
                    "sse queue full, dropping non-terminal event",
                    deployment_id=deployment_id,
                )


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
                _log_lock = asyncio.Lock()

                async def emit_log(
                    level: str, message: str, step_id: str | None = None
                ) -> None:
                    """Persiste log no DB e publica no SSE.

                    Lock garante que flushes concorrentes (ex: asyncio.gather
                    no validate step) nao crashem o SQLAlchemy session.

                    Performance: usa flush (sem commit) pra obter o ID e
                    publica imediatamente no SSE com timestamp local. O
                    commit real acontece no boundary de step (apos execute_step
                    retornar) — reduz de ~100 commits/deploy pra ~10.
                    """
                    if cancel_event.is_set():
                        return
                    async with _log_lock:
                        log = DeploymentLog(
                            deployment_id=deployment_id,
                            level=level,
                            message=message,
                            step_id=step_id,
                        )
                        db.add(log)
                        await db.flush()
                    log_ts = datetime.now(UTC).isoformat()
                    await _publish(
                        dep_id_str,
                        {
                            "type": "log",
                            "deployment_id": dep_id_str,
                            "data": {
                                "id": str(log.id),
                                "level": level,
                                "message": message,
                                "step_id": step_id,
                                "timestamp": log_ts,
                            },
                        },
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
            pipeline = Pipeline(
                company_id=deployment.company_id,
                name=deployment.name,
                description=f"Deploy de {deployment.template_name}",
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
            raise
        except Exception as exc:
            logger.exception("saga run failed", deployment_id=dep_id_str)
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
            _cancellations.pop(dep_id_str, None)


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
