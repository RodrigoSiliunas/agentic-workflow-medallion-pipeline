"""Schemas de observabilidade — metricas agregadas da empresa."""

from pydantic import BaseModel


class DeploymentBreakdown(BaseModel):
    total: int
    success: int
    failed: int
    running: int
    cancelled: int
    avg_duration_seconds: float | None


class PipelineMetrics(BaseModel):
    total: int
    with_databricks_job: int


class ChannelMetrics(BaseModel):
    total: int
    by_channel: dict[str, int]
    connected: int


class ObserverMetrics(BaseModel):
    """Metricas do Observer Agent (mockadas — viriam de medallion.observer.diagnostics)."""

    total_diagnostics: int
    prs_created: int
    dedup_cache_hits: int
    estimated_cost_usd: float
    period_days: int


class ObservabilityMetrics(BaseModel):
    company_id: str
    deployments: DeploymentBreakdown
    pipelines: PipelineMetrics
    channels: ChannelMetrics
    observer: ObserverMetrics
