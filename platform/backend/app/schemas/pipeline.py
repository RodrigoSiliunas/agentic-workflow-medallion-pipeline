"""Schemas de pipeline (request/response)."""

from pydantic import BaseModel


class CreatePipelineRequest(BaseModel):
    name: str
    description: str | None = None
    databricks_job_id: int | None = None
    github_repo: str | None = None


class PipelineResponse(BaseModel):
    id: str
    name: str
    description: str | None
    databricks_job_id: int | None
    github_repo: str | None

    class Config:
        from_attributes = True


class PipelineStatusResponse(BaseModel):
    pipeline_id: str
    name: str
    status: str  # SUCCESS | FAILED | RUNNING | IDLE
    last_run_at: str | None
    next_run_at: str | None
