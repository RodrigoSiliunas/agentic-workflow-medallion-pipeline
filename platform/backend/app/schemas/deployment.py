"""Pydantic schemas para deployments."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class WorkspaceAdvancedConfig(BaseModel):
    """Config opcional do workspace exposta na aba "Avançado" do wizard.

    Campos default-derivados — usuario casual nao precisa preencher nada.
    Cluster sizing respeita driver/worker separados, autoscale opcional,
    policy enforcement e custom tags pra billing tracking.
    """

    root_bucket: str | None = None
    network_cidr: str | None = None
    admin_email: str | None = None
    metastore_id: str | None = None
    # Cluster identity
    cluster_name: str | None = None
    # Cluster sizing — node_type aplica a worker; driver_node_type opcional
    # (None = mesmo tipo do worker)
    cluster_node_type: str | None = None
    cluster_driver_node_type: str | None = None
    cluster_num_workers: int | None = None
    cluster_spark_version: str | None = None
    # Autoscale (se min/max set, sobrepõe num_workers)
    cluster_autoscale_min: int | None = None
    cluster_autoscale_max: int | None = None
    cluster_autotermination_min: int | None = None
    # Policy enforcement (force allowlist + max workers + ttl)
    cluster_policy_id: str | None = None
    # Policy custom JSON — saga registra no workspace + atrela ao cluster.
    # Mutuamente exclusivo com cluster_policy_id (custom tem precedencia).
    cluster_policy_definition: str | None = None
    # Custom tags propagadas pra AWS billing + Databricks usage
    cluster_tags: dict[str, str] | None = None
    # Observer Agent LLM override (per-pipeline). Sem isso, usa default
    # da empresa (company.preferred_provider/model).
    observer_llm_provider: str | None = None
    observer_llm_model: str | None = None


class DeploymentConfigIn(BaseModel):
    name: str
    environment: Literal["dev", "staging", "prod"] = "prod"
    tags: dict[str, str] = Field(default_factory=dict)
    credentials: dict[str, str] = Field(default_factory=dict)
    env_vars: dict[str, str] = Field(default_factory=dict)
    # Workspace selection: existing (skip provisioning) ou new (full saga).
    # Se ausente, default = "new" pra preservar compat com wizard antigo.
    workspace_mode: Literal["existing", "new"] = "new"
    # Modo existing: id do workspace alvo (Databricks Account API)
    workspace_id: str | None = None
    # Modo new: nome customizado do workspace (override do auto company-suffix)
    workspace_name: str | None = None
    advanced: WorkspaceAdvancedConfig | None = None


class DeploymentCreateRequest(BaseModel):
    template_slug: str
    config: DeploymentConfigIn


class DeploymentStepResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    step_id: str
    name: str
    description: str | None
    status: str
    order_index: int
    started_at: datetime | None
    finished_at: datetime | None
    duration_ms: int | None
    error_message: str | None


class DeploymentLogResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    level: str
    message: str
    step_id: str | None
    created_at: datetime


class DeploymentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    template_slug: str
    template_name: str
    name: str
    environment: str
    config: dict
    status: str
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None
    duration_ms: int | None
    pipeline_id: str | None
    steps: list[DeploymentStepResponse] = Field(default_factory=list)
    logs: list[DeploymentLogResponse] = Field(default_factory=list)


class DeploymentListItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    template_slug: str
    template_name: str
    name: str
    environment: str
    status: str
    created_at: datetime
    finished_at: datetime | None
    duration_ms: int | None


class DeploymentEvent(BaseModel):
    """Payload emitido via SSE para um deployment em execucao."""

    type: Literal["step_update", "log", "status_change", "complete", "error"]
    deployment_id: str
    data: dict
