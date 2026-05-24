"""Schemas HTTP do Pipeline Editor."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.services.pipeline_editor.schemas import EditProposal, TransformDraft


class CreateEditSessionRequest(BaseModel):
    title: str | None = None
    target_layers: list[str] = Field(default_factory=lambda: ["silver"])
    base_ref: str = "dev"


class EditSessionResponse(BaseModel):
    id: uuid.UUID
    pipeline_id: uuid.UUID
    title: str
    status: str
    target_layers: list[str]
    base_ref: str | None
    draft_branch: str | None
    current_version_id: uuid.UUID | None
    created_at: datetime | None = None
    updated_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)


class EditMessageRequest(BaseModel):
    message: str
    draft: TransformDraft | None = None


class EditMessageResponse(BaseModel):
    session_id: uuid.UUID
    message: str
    proposal: EditProposal
    version_id: uuid.UUID


class DraftUpdateRequest(BaseModel):
    draft: TransformDraft


class EditVersionResponse(BaseModel):
    id: uuid.UUID
    session_id: uuid.UUID
    version_number: int
    draft: dict[str, Any]
    generated_files: dict[str, Any] | None
    validation_result: dict[str, Any] | None
    preview_result: dict[str, Any] | None
    pr_metadata: dict[str, Any] | None
    created_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)


class PreviewRequest(BaseModel):
    version_id: uuid.UUID | None = None
    sample_rows: int = Field(default=50, ge=1, le=5000)


class ExportRequest(BaseModel):
    version_id: uuid.UUID | None = None
    format: str = Field(pattern="^(csv|parquet)$")


class ShareRequest(BaseModel):
    session_id: uuid.UUID | None = None
    artifact_id: uuid.UUID | None = None
    role: str = "viewer"
    expires_at: datetime | None = None


class ApproveRequest(BaseModel):
    version_id: uuid.UUID | None = None
    create_pr: bool = True


class RevertRequest(BaseModel):
    version_id: uuid.UUID | None = None
    mode: str = Field(default="draft", pattern="^(draft|close_pr|revert_pr)$")
