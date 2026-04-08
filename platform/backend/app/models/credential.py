"""Company credentials — criptografadas com Fernet."""

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDMixin


class CompanyCredential(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "company_credentials"

    company_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False
    )
    credential_type: Mapped[str] = mapped_column(String(100), nullable=False)
    # Tipos: anthropic_api_key, discord_bot_token, telegram_bot_token,
    #        github_token, github_repo, databricks_host, databricks_token
    encrypted_value: Mapped[str] = mapped_column(Text, nullable=False)
    is_valid: Mapped[bool] = mapped_column(Boolean, default=False)
    last_tested_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Relationships
    company = relationship("Company", back_populates="credentials")
