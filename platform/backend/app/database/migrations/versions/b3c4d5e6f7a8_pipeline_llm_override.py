"""pipeline_llm_override

Adiciona preferred_provider + preferred_model em pipelines pra runtime
override (sem precisar redeploy da saga).

Revision ID: b3c4d5e6f7a8
Revises: a2b3c4d5e6f7
Create Date: 2026-04-23 23:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "b3c4d5e6f7a8"
down_revision: Union[str, Sequence[str], None] = "a2b3c4d5e6f7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "pipelines",
        sa.Column("preferred_provider", sa.String(length=50), nullable=True),
    )
    op.add_column(
        "pipelines",
        sa.Column("preferred_model", sa.String(length=100), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("pipelines", "preferred_model")
    op.drop_column("pipelines", "preferred_provider")
