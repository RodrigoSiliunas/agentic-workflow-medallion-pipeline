"""Template model — templates do marketplace one-click deploy."""

from sqlalchemy import Boolean, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDMixin


class Template(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "templates"

    slug: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    tagline: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    category: Mapped[str] = mapped_column(String(50), nullable=False)
    tags: Mapped[list] = mapped_column(JSONB, default=list)
    icon: Mapped[str] = mapped_column(String(100), nullable=False)
    icon_bg: Mapped[str] = mapped_column(String(20), nullable=False)
    version: Mapped[str] = mapped_column(String(20), nullable=False)
    author: Mapped[str] = mapped_column(String(100), nullable=False)
    deploy_count: Mapped[int] = mapped_column(Integer, default=0)
    duration_estimate: Mapped[str] = mapped_column(String(50), nullable=False)
    architecture_bullets: Mapped[list] = mapped_column(JSONB, default=list)
    env_schema: Mapped[list] = mapped_column(JSONB, default=list)
    changelog: Mapped[list] = mapped_column(JSONB, default=list)
    published: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
