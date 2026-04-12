"""Pydantic schemas para deployments."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class DeploymentConfigIn(BaseModel):
    name: str
    environment: Literal["dev", "staging", "prod"] = "prod"
    tags: dict[str, str] = Field(default_factory=dict)
    credentials: dict[str, str] = Field(default_factory=dict)
    env_vars: dict[str, str] = Field(default_factory=dict)


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
