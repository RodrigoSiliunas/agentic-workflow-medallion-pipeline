"""Pydantic schemas para deployments."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class WorkspaceAdvancedConfig(BaseModel):
    """Config opcional do workspace exposta na aba "Avançado" do wizard.

    Campos default-derivados — usuario casual nao precisa preencher nada:
    - root_bucket: default `{s3_bucket}-root`
    - network_cidr: default 10.0.0.0/16
    - admin_email: default administrator@idlehub.com.br
    - metastore_id: default = auto-discover por regiao via Account API
    - cluster_node_type: default m5d.large (ver useClusterTypes catalog)
    - cluster_num_workers: default 2
    - cluster_spark_version: default 15.4 LTS
    """

    root_bucket: str | None = None
    network_cidr: str | None = None
    admin_email: str | None = None
    metastore_id: str | None = None
    cluster_node_type: str | None = None
    cluster_num_workers: int | None = None
    cluster_spark_version: str | None = None
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
