"""Schemas de chat (request/response)."""

from pydantic import BaseModel


class SendMessageRequest(BaseModel):
    thread_id: str
    message: str
    pipeline_job_id: int | None = None


class CreateThreadRequest(BaseModel):
    pipeline_id: str


class ThreadResponse(BaseModel):
    id: str
    pipeline_id: str
    title: str | None
    is_active: bool
    created_at: str
    updated_at: str

    class Config:
        from_attributes = True


class MessageResponse(BaseModel):
    id: str
    role: str
    content: str
    actions: list | None = None
    channel: str | None
    model: str | None
    created_at: str

    class Config:
        from_attributes = True
