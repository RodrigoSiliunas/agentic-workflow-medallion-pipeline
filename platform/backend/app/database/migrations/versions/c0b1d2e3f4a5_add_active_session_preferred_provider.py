"""add_active_session_preferred_provider

Migration f1a2b3c4d5e6_add_multi_llm_provider adicionou preferred_provider em
companies e omni_instances mas esqueceu de active_sessions. Model
ActiveSession.preferred_provider (channel.py:33) referencia a coluna que
nunca foi criada -> slash commands quebravam com:

  sqlalchemy.exc.ProgrammingError: column active_sessions.preferred_provider
  does not exist

Revision ID: c0b1d2e3f4a5
Revises: b9d4e5f6a7c1
Create Date: 2026-05-12 06:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "c0b1d2e3f4a5"
down_revision: Union[str, Sequence[str], None] = "b9d4e5f6a7c1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "active_sessions",
        sa.Column("preferred_provider", sa.String(length=50), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("active_sessions", "preferred_provider")
