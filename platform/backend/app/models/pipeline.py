"""Pipeline model — pipelines registrados por empresa."""

import uuid

from sqlalchemy import BigInteger, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDMixin


class Pipeline(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "pipelines"

    company_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    databricks_job_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    github_repo: Mapped[str | None] = mapped_column(String(500), nullable=True)
    config: Mapped[dict | None] = mapped_column(JSONB, default={})
    # Runtime LLM override per-pipeline (chat agent + Observer)
    # Vazio = usa default da empresa
    preferred_provider: Mapped[str | None] = mapped_column(String(50), nullable=True)
    preferred_model: Mapped[str | None] = mapped_column(String(100), nullable=True)


class PipelineContextCache(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "pipeline_context_cache"

    pipeline_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("pipelines.id", ondelete="CASCADE"), nullable=False
    )
    context_type: Mapped[str] = mapped_column(String(50), nullable=False)
    content: Mapped[dict] = mapped_column(JSONB, nullable=False)
    token_estimate: Mapped[int | None] = mapped_column(nullable=True)
