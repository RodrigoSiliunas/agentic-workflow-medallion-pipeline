"""Modelos tenant-scoped do Pipeline Editor."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDMixin


class PipelineEditSession(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "pipeline_edit_sessions"
    __table_args__ = (
        Index("ix_pipeline_edit_sessions_tenant_pipeline", "company_id", "pipeline_id"),
    )

    company_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False
    )
    pipeline_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("pipelines.id", ondelete="CASCADE"), nullable=False
    )
    created_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(50), default="draft", nullable=False)
    target_layers: Mapped[list] = mapped_column(JSONB, default=list)
    base_ref: Mapped[str | None] = mapped_column(String(100), nullable=True)
    draft_branch: Mapped[str | None] = mapped_column(String(255), nullable=True)
    current_version_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)


class PipelineEditMessage(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "pipeline_edit_messages"
    __table_args__ = (
        Index("ix_pipeline_edit_messages_session_created", "session_id", "created_at"),
    )

    company_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False
    )
    pipeline_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("pipelines.id", ondelete="CASCADE"), nullable=False
    )
    session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("pipeline_edit_sessions.id", ondelete="CASCADE"),
        nullable=False,
    )
    role: Mapped[str] = mapped_column(String(20), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    tool_events: Mapped[list | None] = mapped_column(JSONB, default=list)
    structured_state: Mapped[dict | None] = mapped_column(JSONB, default=dict)


class PipelineEditVersion(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "pipeline_edit_versions"
    __table_args__ = (
        Index("ix_pipeline_edit_versions_session", "session_id", "created_at"),
    )

    company_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False
    )
    pipeline_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("pipelines.id", ondelete="CASCADE"), nullable=False
    )
    session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("pipeline_edit_sessions.id", ondelete="CASCADE"),
        nullable=False,
    )
    version_number: Mapped[int] = mapped_column(nullable=False, default=1)
    draft: Mapped[dict] = mapped_column(JSONB, nullable=False)
    generated_files: Mapped[dict | None] = mapped_column(JSONB, default=dict)
    validation_result: Mapped[dict | None] = mapped_column(JSONB, default=dict)
    preview_result: Mapped[dict | None] = mapped_column(JSONB, default=dict)
    pr_metadata: Mapped[dict | None] = mapped_column(JSONB, default=dict)


class PipelineEditArtifact(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "pipeline_edit_artifacts"
    __table_args__ = (
        Index("ix_pipeline_edit_artifacts_session", "session_id", "artifact_type"),
    )

    company_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False
    )
    pipeline_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("pipelines.id", ondelete="CASCADE"), nullable=False
    )
    session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("pipeline_edit_sessions.id", ondelete="CASCADE"),
        nullable=False,
    )
    version_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    artifact_type: Mapped[str] = mapped_column(String(50), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    content: Mapped[dict] = mapped_column(JSONB, nullable=False)
    storage_uri: Mapped[str | None] = mapped_column(Text, nullable=True)


class PipelineShare(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "pipeline_shares"
    __table_args__ = (
        Index("ix_pipeline_shares_token", "share_token", unique=True),
    )

    company_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False
    )
    pipeline_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("pipelines.id", ondelete="CASCADE"), nullable=False
    )
    session_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    artifact_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    created_by_user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    share_token: Mapped[str] = mapped_column(String(128), nullable=False)
    role: Mapped[str] = mapped_column(String(50), default="viewer")
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
