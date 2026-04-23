"""Company model — raiz do multi-tenant."""

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDMixin


class Company(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "companies"

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    # Multi-LLM: provider e model separados (provider determina SDK + API key,
    # model eh string literal aceita pela API daquele provider)
    preferred_provider: Mapped[str] = mapped_column(String(50), default="anthropic")
    preferred_model: Mapped[str] = mapped_column(
        String(100), default="claude-sonnet-4-6"
    )

    # Relationships
    users = relationship("User", back_populates="company", cascade="all, delete-orphan")
    credentials = relationship(
        "CompanyCredential", back_populates="company", cascade="all, delete-orphan"
    )
