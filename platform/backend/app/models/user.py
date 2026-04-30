"""User model com RBAC."""

import uuid

from sqlalchemy import Boolean, ForeignKey, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDMixin

ROLE_HIERARCHY = {"root": 4, "admin": 3, "editor": 2, "viewer": 1}

ROLE_PERMISSIONS = {
    "root": [
        "manage_company", "manage_users", "manage_settings", "manage_credentials",
        "manage_pipelines", "chat", "create_pr", "trigger_run", "send_notification",
        "view_audit_log",
    ],
    "admin": [
        "manage_users", "manage_settings", "manage_credentials", "manage_pipelines",
        "chat", "create_pr", "trigger_run", "send_notification", "view_audit_log",
    ],
    "editor": ["chat", "create_pr", "trigger_run", "send_notification"],
    "viewer": ["chat"],
}


class User(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "users"
    # Email unico por empresa, NAO global. Permite que o email "ceo@x.com"
    # exista em multiplas companies sem squatting (login disambigua via
    # company_slug). Migration b9d4e5f6a7c1 troca o unique global por composto.
    __table_args__ = (
        UniqueConstraint("company_id", "email", name="uq_users_company_email"),
    )

    company_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False
    )
    email: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(50), default="viewer")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    # Relationships
    company = relationship("Company", back_populates="users")
