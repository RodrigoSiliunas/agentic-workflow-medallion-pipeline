"""Schemas de chat (request/response)."""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class SendMessageRequest(BaseModel):
    thread_id: str
    message: str
    pipeline_job_id: int | None = None
    model: str | None = None  # ID literal (claude-opus-4-7, gpt-5, gemini-2.5-pro)
    provider: str | None = None  # "anthropic" | "openai" | "google"


class CreateThreadRequest(BaseModel):
    pipeline_id: str


class ThreadResponse(BaseModel):
    id: uuid.UUID
    pipeline_id: uuid.UUID
    title: str | None
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class MessageResponse(BaseModel):
    id: uuid.UUID
    role: str
    content: str
    actions: list | None = None
    channel: str | None
    model: str | None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
