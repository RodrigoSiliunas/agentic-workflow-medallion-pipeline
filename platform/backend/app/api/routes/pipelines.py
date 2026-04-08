"""Pipeline routes — CRUD + status."""

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import AuthContext, get_current_user, require_permission
from app.database.session import get_db
from app.models.pipeline import Pipeline
from app.schemas.pipeline import CreatePipelineRequest, PipelineResponse, PipelineStatusResponse
from app.services.databricks_service import DatabricksService

router = APIRouter()


@router.get("", response_model=list[PipelineResponse])
async def list_pipelines(
    auth: AuthContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Lista pipelines da empresa (todos os roles podem ver)."""
    result = await db.execute(
        select(Pipeline).where(Pipeline.company_id == auth.company_id).order_by(Pipeline.name)
    )
    return result.scalars().all()


@router.post("", response_model=PipelineResponse, status_code=201)
async def create_pipeline(
    data: CreatePipelineRequest,
    auth: AuthContext = Depends(require_permission("manage_pipelines")),
    db: AsyncSession = Depends(get_db),
):
    """Registra novo pipeline (admin only)."""
    pipeline = Pipeline(
        company_id=auth.company_id,
        name=data.name,
        description=data.description,
        databricks_job_id=data.databricks_job_id,
        github_repo=data.github_repo,
    )
    db.add(pipeline)
    await db.flush()
    return pipeline


@router.get("/{pipeline_id}/status", response_model=PipelineStatusResponse)
async def get_pipeline_status(
    pipeline_id: uuid.UUID,
    auth: AuthContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Retorna status do pipeline via Databricks."""
    result = await db.execute(
        select(Pipeline).where(
            Pipeline.id == pipeline_id, Pipeline.company_id == auth.company_id
        )
    )
    pipeline = result.scalar_one_or_none()
    if not pipeline:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Pipeline nao encontrado")

    if not pipeline.databricks_job_id:
        return PipelineStatusResponse(
            pipeline_id=str(pipeline.id),
            name=pipeline.name,
            status="NOT_CONFIGURED",
            last_run_at=None,
            next_run_at=None,
        )

    service = DatabricksService(db, auth.company_id)
    summary = await service.get_pipeline_summary(pipeline.databricks_job_id)

    return PipelineStatusResponse(
        pipeline_id=str(pipeline.id),
        name=pipeline.name,
        status=summary.get("status", "UNKNOWN"),
        last_run_at=str(summary.get("last_run_at")) if summary.get("last_run_at") else None,
        next_run_at=None,
    )
