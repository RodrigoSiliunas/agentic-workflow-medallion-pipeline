"""add_multi_llm_provider

Adiciona preferred_provider em companies + active_sessions + omni_instances.
Aumenta preferred_model de String(50) pra String(100) (pros novos model IDs
tipo gemini-2.5-pro, claude-opus-4-7, gpt-5-mini).

Backfill:
- companies.preferred_provider = "anthropic" (default explicito)
- companies.preferred_model: "sonnet" -> "claude-sonnet-4-6", "opus" -> "claude-opus-4-7",
  "haiku" -> "claude-haiku-4-5"

Revision ID: f1a2b3c4d5e6
Revises: 74d734fbdf07
Create Date: 2026-04-23 22:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "f1a2b3c4d5e6"
down_revision: Union[str, Sequence[str], None] = "74d734fbdf07"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Companies: novo preferred_provider + alargar preferred_model
    op.add_column(
        "companies",
        sa.Column(
            "preferred_provider",
            sa.String(length=50),
            nullable=False,
            server_default="anthropic",
        ),
    )
    op.alter_column(
        "companies",
        "preferred_model",
        existing_type=sa.String(length=50),
        type_=sa.String(length=100),
        existing_nullable=False,
    )
    # Backfill: legacy short names -> full model IDs
    op.execute(
        "UPDATE companies SET preferred_model = 'claude-sonnet-4-6' "
        "WHERE preferred_model = 'sonnet'"
    )
    op.execute(
        "UPDATE companies SET preferred_model = 'claude-opus-4-7' "
        "WHERE preferred_model = 'opus'"
    )
    op.execute(
        "UPDATE companies SET preferred_model = 'claude-haiku-4-5' "
        "WHERE preferred_model = 'haiku'"
    )

    # 2. ActiveSession: alargar preferred_model
    op.alter_column(
        "active_sessions",
        "preferred_model",
        existing_type=sa.String(length=50),
        type_=sa.String(length=100),
        existing_nullable=True,
    )

    # 3. OmniInstance: novos preferred_provider + preferred_model
    op.add_column(
        "omni_instances",
        sa.Column("preferred_provider", sa.String(length=50), nullable=True),
    )
    op.add_column(
        "omni_instances",
        sa.Column("preferred_model", sa.String(length=100), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("omni_instances", "preferred_model")
    op.drop_column("omni_instances", "preferred_provider")
    op.alter_column(
        "active_sessions",
        "preferred_model",
        existing_type=sa.String(length=100),
        type_=sa.String(length=50),
        existing_nullable=True,
    )
    op.alter_column(
        "companies",
        "preferred_model",
        existing_type=sa.String(length=100),
        type_=sa.String(length=50),
        existing_nullable=False,
    )
    op.drop_column("companies", "preferred_provider")
