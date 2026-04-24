"""CustomLLMEndpoint — endpoints OpenAI-compatible self-hosted ou de terceiros.

Cada empresa pode cadastrar N endpoints (Ollama local, vLLM remoto, OpenRouter,
Together, etc). API key cifrada via Fernet (mesmo pattern de CompanyCredential).
Models eh JSONB pra evitar tabela filha — lista descoberta via GET /v1/models
no test_connection.
"""

import datetime as dt
import uuid

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDMixin


class CustomLLMEndpoint(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "custom_llm_endpoints"
    __table_args__ = (
        UniqueConstraint("company_id", "name", name="uq_custom_llm_endpoint_name"),
    )

    company_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False,
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    base_url: Mapped[str] = mapped_column(String(500), nullable=False)
    encrypted_api_key: Mapped[str | None] = mapped_column(Text, nullable=True)
    models: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    last_tested_at: Mapped[dt.datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_test_status: Mapped[str | None] = mapped_column(String(50), nullable=True)
