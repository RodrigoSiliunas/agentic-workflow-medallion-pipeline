"""Observability routes — metricas agregadas da empresa para dashboards."""

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import AuthContext, get_current_user
from app.database.session import get_db
from app.models.channel import OmniInstance
from app.models.deployment import Deployment
from app.models.pipeline import Pipeline
from app.schemas.observability import (
    ChannelMetrics,
    DeploymentBreakdown,
    ObservabilityMetrics,
    ObserverMetrics,
    PipelineMetrics,
)

router = APIRouter()


@router.get("/metrics", response_model=ObservabilityMetrics)
async def get_metrics(
    auth: AuthContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Retorna agregacoes de deployments, pipelines, channels e Observer."""
    deployments = await _deployment_breakdown(db, auth.company_id)
    pipelines = await _pipeline_metrics(db, auth.company_id)
    channels = await _channel_metrics(db, auth.company_id)
    observer = _observer_metrics_mock()

    return ObservabilityMetrics(
        company_id=str(auth.company_id),
        deployments=deployments,
        pipelines=pipelines,
        channels=channels,
        observer=observer,
    )


async def _deployment_breakdown(db: AsyncSession, company_id) -> DeploymentBreakdown:
    result = await db.execute(
        select(Deployment.status, func.count(), func.avg(Deployment.duration_ms))
        .where(Deployment.company_id == company_id)
        .group_by(Deployment.status)
    )
    rows = result.all()

    counts = {"success": 0, "failed": 0, "running": 0, "cancelled": 0, "pending": 0}
    total = 0
    sum_success_ms = 0.0
    n_success = 0

    for status, count, avg_ms in rows:
        counts[status] = counts.get(status, 0) + count
        total += count
        if status == "success" and avg_ms is not None:
            sum_success_ms += float(avg_ms) * count
            n_success += count

    avg_seconds = (sum_success_ms / n_success / 1000.0) if n_success else None

    return DeploymentBreakdown(
        total=total,
        success=counts.get("success", 0),
        failed=counts.get("failed", 0),
        running=counts.get("running", 0),
        cancelled=counts.get("cancelled", 0),
        avg_duration_seconds=avg_seconds,
    )


async def _pipeline_metrics(db: AsyncSession, company_id) -> PipelineMetrics:
    total_result = await db.execute(
        select(func.count()).select_from(Pipeline).where(Pipeline.company_id == company_id)
    )
    total = int(total_result.scalar() or 0)

    with_job_result = await db.execute(
        select(func.count())
        .select_from(Pipeline)
        .where(
            Pipeline.company_id == company_id,
            Pipeline.databricks_job_id.isnot(None),
        )
    )
    with_job = int(with_job_result.scalar() or 0)

    return PipelineMetrics(total=total, with_databricks_job=with_job)


async def _channel_metrics(db: AsyncSession, company_id) -> ChannelMetrics:
    result = await db.execute(
        select(OmniInstance.channel, OmniInstance.state)
        .where(OmniInstance.company_id == company_id)
    )
    rows = result.all()

    total = len(rows)
    connected = 0
    by_channel: dict[str, int] = {}
    for channel, state in rows:
        by_channel[channel] = by_channel.get(channel, 0) + 1
        if state == "connected":
            connected += 1

    return ChannelMetrics(total=total, by_channel=by_channel, connected=connected)


def _observer_metrics_mock() -> ObserverMetrics:
    """Retorna metricas mockadas do Observer Agent.

    Real wiring futuro: consultar a tabela Delta `medallion.observer.diagnostics`
    via Databricks SQL connector, agregar por timestamp e provider.
    """
    return ObserverMetrics(
        total_diagnostics=23,
        prs_created=19,
        dedup_cache_hits=18,
        estimated_cost_usd=4.82,
        period_days=30,
    )
