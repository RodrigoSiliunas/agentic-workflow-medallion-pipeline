"""Schemas de pipeline (request/response)."""

import uuid

from pydantic import BaseModel, ConfigDict


class CreatePipelineRequest(BaseModel):
    name: str
    description: str | None = None
    databricks_job_id: int | None = None
    github_repo: str | None = None


class PipelineResponse(BaseModel):
    id: uuid.UUID
    name: str
    description: str | None
    databricks_job_id: int | None
    github_repo: str | None
    status: str = "IDLE"

    model_config = ConfigDict(from_attributes=True)


class PipelineStatusResponse(BaseModel):
    pipeline_id: str
    name: str
    status: str  # SUCCESS | FAILED | RUNNING | IDLE
    last_run_at: str | None
    next_run_at: str | None
