"""Deployments routes — one-click deploy com saga assincrona + SSE."""

import asyncio
import json
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import AuthContext, get_current_user
from app.database.session import get_db
from app.models.deployment import Deployment, DeploymentLog, DeploymentStep
from app.models.template import Template
from app.schemas.deployment import (
    DeploymentCreateRequest,
    DeploymentListItem,
    DeploymentResponse,
)
from app.services.credential_service import DEPLOY_CREDENTIAL_TYPES, CredentialService
from app.services.deployment_saga import (
    SAGA_BLUEPRINT,
    request_cancel,
    run_saga,
    subscribe,
    unsubscribe,
)
from app.services.real_saga.base import DeploymentCredentials

router = APIRouter()


@router.get("/blueprint")
async def get_blueprint():
    """Retorna o SAGA_BLUEPRINT — single source of truth dos steps do deploy.

    O frontend consome esse endpoint pra renderizar a lista de steps no
    DeployProgress e no mock runner, ao inves de hardcodar os steps no
    frontend store.
    """
    return SAGA_BLUEPRINT


@router.get("", response_model=list[DeploymentListItem])
async def list_deployments(
    auth: AuthContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Lista deployments da empresa (summary sem logs aninhados)."""
    result = await db.execute(
        select(Deployment)
        .where(Deployment.company_id == auth.company_id)
        .order_by(Deployment.created_at.desc())
    )
    deployments = result.scalars().all()
    return [
        {
            "id": str(d.id),
            "template_slug": d.template_slug,
            "template_name": d.template_name,
            "name": d.name,
            "environment": d.environment,
            "status": d.status,
            "created_at": d.created_at,
            "finished_at": d.finished_at,
            "duration_ms": d.duration_ms,
        }
        for d in deployments
    ]


@router.get("/{deployment_id}", response_model=DeploymentResponse)
async def get_deployment(
    deployment_id: uuid.UUID,
    auth: AuthContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Detalhe de um deployment com steps + logs aninhados."""
    deployment = await _load_owned(db, deployment_id, auth.company_id)

    steps_result = await db.execute(
        select(DeploymentStep)
        .where(DeploymentStep.deployment_id == deployment_id)
        .order_by(DeploymentStep.order_index)
    )
    steps = steps_result.scalars().all()

    logs_result = await db.execute(
        select(DeploymentLog)
        .where(DeploymentLog.deployment_id == deployment_id)
        .order_by(DeploymentLog.created_at)
    )
    logs = logs_result.scalars().all()

    return _serialize(deployment, steps, logs)


@router.post("", response_model=DeploymentResponse, status_code=201)
async def create_deployment(
    data: DeploymentCreateRequest,
    auth: AuthContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Cria um deployment e dispara a saga em background."""
    template_result = await db.execute(
        select(Template).where(Template.slug == data.template_slug)
    )
    template = template_result.scalar_one_or_none()
    if not template:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Template nao encontrado",
        )

    # Resolve credenciais: override vindo do wizard > company_credentials.
    # Precisa ser feito ANTES do saga disparar pq o saga roda em outra
    # session e nao tem o request body disponivel.
    # Bulk: 1 query pra todas as credenciais da empresa (em vez de N sequenciais).
    cred_service = CredentialService(db)
    override_creds = data.config.credentials or {}
    company_creds = await cred_service.get_all_decrypted(auth.company_id)
    credential_sources: dict[str, str] = {}
    resolved: dict[str, str] = {}

    for cred_type in DEPLOY_CREDENTIAL_TYPES:
        override_value = override_creds.get(cred_type, "")
        if isinstance(override_value, str) and override_value.strip():
            credential_sources[cred_type] = "override"
            resolved[cred_type] = override_value.strip()
        elif company_creds.get(cred_type):
            credential_sources[cred_type] = "company"
            resolved[cred_type] = company_creds[cred_type]
        else:
            credential_sources[cred_type] = "missing"

    # Anthropic + github_repo tambem viajam no objeto (nao fazem parte do
    # DEPLOY_CREDENTIAL_TYPES mas o RealSagaRunner precisa deles).
    for extra in ("anthropic_api_key", "github_repo"):
        if company_creds.get(extra):
            resolved[extra] = company_creds[extra]

    resolved_credentials = DeploymentCredentials(
        aws_access_key_id=resolved.get("aws_access_key_id"),
        aws_secret_access_key=resolved.get("aws_secret_access_key"),
        aws_region=resolved.get("aws_region"),
        databricks_host=resolved.get("databricks_host"),
        databricks_token=resolved.get("databricks_token"),
        github_token=resolved.get("github_token"),
        github_repo=resolved.get("github_repo"),
        anthropic_api_key=resolved.get("anthropic_api_key"),
    )

    # Merge env_vars com workspace_mode + advanced — saga steps consomem
    # tudo via ctx.env_vars(). Mantem os opcionais ausentes fora do dict
    # pra steps que checam `if env.get("workspace_mode") == "existing"`
    # nao serem afetados quando o wizard antigo nao envia esses campos.
    merged_env: dict[str, str] = dict(data.config.env_vars or {})
    merged_env["workspace_mode"] = data.config.workspace_mode
    if data.config.workspace_id:
        merged_env["workspace_id"] = data.config.workspace_id
    if data.config.workspace_name:
        merged_env["workspace_name"] = data.config.workspace_name
    adv = data.config.advanced
    if adv:
        if adv.root_bucket:
            merged_env["workspace_root_bucket"] = adv.root_bucket
        if adv.network_cidr:
            merged_env["network_cidr"] = adv.network_cidr
        if adv.admin_email:
            merged_env["admin_email"] = adv.admin_email
        if adv.metastore_id:
            merged_env["databricks_metastore_id"] = adv.metastore_id
        if adv.cluster_node_type:
            merged_env["cluster_node_type"] = adv.cluster_node_type
        if adv.cluster_num_workers is not None:
            merged_env["cluster_num_workers"] = str(adv.cluster_num_workers)
        if adv.cluster_spark_version:
            merged_env["cluster_spark_version"] = adv.cluster_spark_version
        if adv.observer_llm_provider:
            merged_env["observer_llm_provider"] = adv.observer_llm_provider
        if adv.observer_llm_model:
            merged_env["observer_llm_model"] = adv.observer_llm_model

    deployment = Deployment(
        company_id=auth.company_id,
        user_id=auth.user_id,
        template_slug=template.slug,
        template_name=template.name,
        name=data.config.name,
        environment=data.config.environment,
        config={
            "tags": data.config.tags,
            "credentials": {k: "***" for k in override_creds},  # mascarado
            "credential_sources": credential_sources,
            "env_vars": merged_env,
            "workspace_mode": data.config.workspace_mode,
        },
        status="pending",
    )
    db.add(deployment)
    await db.flush()
    await db.refresh(deployment)
    deployment_id = deployment.id

    # Commit explicito antes de disparar a saga — a background task abre
    # sua propria session e precisa enxergar o deployment ja persistido.
    await db.commit()

    # As credenciais resolvidas viajam via closure do asyncio.create_task —
    # ficam apenas em memoria, nunca tocam o DB decriptadas.
    asyncio.create_task(run_saga(deployment_id, credentials=resolved_credentials))

    return _serialize(deployment, [], [])


@router.post("/{deployment_id}/cancel", status_code=204)
async def cancel_deployment(
    deployment_id: uuid.UUID,
    auth: AuthContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Sinaliza cancelamento da saga."""
    await _load_owned(db, deployment_id, auth.company_id)
    request_cancel(str(deployment_id))


@router.patch("/{deployment_id}")
async def update_deployment(
    deployment_id: uuid.UUID,
    data: dict,
    auth: AuthContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Atualiza nome do deployment."""
    deployment = await _load_owned(db, deployment_id, auth.company_id)
    if "name" in data:
        deployment.name = data["name"]
        if deployment.config:
            deployment.config = {**deployment.config, "name": data["name"]}
    await db.commit()
    return {"status": "updated"}


@router.delete("/{deployment_id}", status_code=204)
async def delete_deployment(
    deployment_id: uuid.UUID,
    auth: AuthContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Exclui um deployment e seus steps/logs (CASCADE).

    Se o deployment esta running, cancela a saga primeiro.
    """
    deployment = await _load_owned(db, deployment_id, auth.company_id)
    if deployment.status in ("pending", "running"):
        request_cancel(str(deployment_id))

    # CASCADE: deployment_steps + deployment_logs sao deletados pelo FK ondelete
    await db.delete(deployment)
    await db.commit()


@router.get("/{deployment_id}/events")
async def stream_deployment_events(
    deployment_id: uuid.UUID,
    auth: AuthContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """SSE stream com eventos reativos da saga (steps + logs + status)."""
    await _load_owned(db, deployment_id, auth.company_id)

    dep_id_str = str(deployment_id)
    queue = subscribe(dep_id_str)

    async def event_generator():
        try:
            # heartbeat inicial
            yield f"data: {json.dumps({'type': 'connected', 'deployment_id': dep_id_str})}\n\n"
            while True:
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=30.0)
                except TimeoutError:
                    yield ": heartbeat\n\n"
                    continue
                yield f"data: {json.dumps(event)}\n\n"
                if event.get("type") in ("complete", "error") or (
                    event.get("type") == "status_change"
                    and event.get("data", {}).get("status") in ("success", "failed", "cancelled")
                ):
                    break
        finally:
            unsubscribe(dep_id_str, queue)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


async def _load_owned(
    db: AsyncSession, deployment_id: uuid.UUID, company_id: uuid.UUID
) -> Deployment:
    result = await db.execute(
        select(Deployment).where(
            Deployment.id == deployment_id,
            Deployment.company_id == company_id,
        )
    )
    deployment = result.scalar_one_or_none()
    if not deployment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Deployment nao encontrado",
        )
    return deployment


def _serialize(
    deployment: Deployment,
    steps: list[DeploymentStep],
    logs: list[DeploymentLog],
) -> dict:
    return {
        "id": str(deployment.id),
        "template_slug": deployment.template_slug,
        "template_name": deployment.template_name,
        "name": deployment.name,
        "environment": deployment.environment,
        "config": deployment.config or {},
        "status": deployment.status,
        "created_at": deployment.created_at,
        "started_at": deployment.started_at,
        "finished_at": deployment.finished_at,
        "duration_ms": deployment.duration_ms,
        "pipeline_id": str(deployment.pipeline_id) if deployment.pipeline_id else None,
        "steps": [
            {
                "id": str(s.id),
                "step_id": s.step_id,
                "name": s.name,
                "description": s.description,
                "status": s.status,
                "order_index": s.order_index,
                "started_at": s.started_at,
                "finished_at": s.finished_at,
                "duration_ms": s.duration_ms,
                "error_message": s.error_message,
            }
            for s in steps
        ],
        "logs": [
            {
                "id": str(log.id),
                "level": log.level,
                "message": log.message,
                "step_id": log.step_id,
                "created_at": log.created_at,
            }
            for log in logs
        ],
    }
