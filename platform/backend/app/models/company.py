"""Company model — raiz do multi-tenant."""

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDMixin


class Company(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "companies"

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    preferred_model: Mapped[str] = mapped_column(String(50), default="sonnet")

    # Relationships
    users = relationship("User", back_populates="company", cascade="all, delete-orphan")
    credentials = relationship(
        "CompanyCredential", back_populates="company", cascade="all, delete-orphan"
    )
