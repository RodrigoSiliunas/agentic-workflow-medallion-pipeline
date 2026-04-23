"""Channel models — sessoes ativas, identidades cross-channel e instancias Omni."""

import datetime as dt
import uuid

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDMixin


class ActiveSession(Base, UUIDMixin, TimestampMixin):
    """Mapeia usuario+canal para thread ativo naquele canal."""

    __tablename__ = "active_sessions"
    __table_args__ = (
        Index("ix_active_sessions_user_channel", "user_id", "channel"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    channel: Mapped[str] = mapped_column(String(50), nullable=False)
    channel_user_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    active_thread_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("threads.id", ondelete="SET NULL"), nullable=True
    )
    active_pipeline_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("pipelines.id", ondelete="SET NULL"), nullable=True
    )
    preferred_model: Mapped[str | None] = mapped_column(String(100), nullable=True)
    preferred_provider: Mapped[str | None] = mapped_column(String(50), nullable=True)


class ChannelIdentity(Base, UUIDMixin, TimestampMixin):
    """Vincula identidade externa (phone, discord_id) ao usuario."""

    __tablename__ = "channel_identities"
    __table_args__ = (
        Index("ix_channel_identities_lookup", "channel", "channel_user_id", unique=True),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    channel: Mapped[str] = mapped_column(String(50), nullable=False)
    channel_user_id: Mapped[str] = mapped_column(String(255), nullable=False)
    verified: Mapped[bool] = mapped_column(Boolean, default=False)


class OmniInstance(Base, UUIDMixin, TimestampMixin):
    """Instancia Omni conectada (WhatsApp/Discord/Telegram) por empresa.

    Persiste metadata local sobre instancias criadas via OmniService.
    O `omni_instance_id` e o identificador retornado pelo proprio Omni
    e usado em todas as chamadas subsequentes (connect, qr, send_message).
    """

    __tablename__ = "omni_instances"

    company_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False
    )
    omni_instance_id: Mapped[str | None] = mapped_column(
        String(255), nullable=True, index=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    channel: Mapped[str] = mapped_column(String(50), nullable=False)
    state: Mapped[str] = mapped_column(
        String(20), nullable=False, default="connecting", index=True
    )
    last_sync_at: Mapped[dt.datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_error: Mapped[str | None] = mapped_column(String(500), nullable=True)
    # Multi-LLM override per instancia (ex: WhatsApp usa Gemini Flash, web usa Opus)
    preferred_provider: Mapped[str | None] = mapped_column(String(50), nullable=True)
    preferred_model: Mapped[str | None] = mapped_column(String(100), nullable=True)
