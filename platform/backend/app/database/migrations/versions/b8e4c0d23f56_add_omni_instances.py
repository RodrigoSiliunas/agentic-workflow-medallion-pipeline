"""add_omni_instances

Revision ID: b8e4c0d23f56
Revises: a7f3d9b12e45
Create Date: 2026-04-10 15:00:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b8e4c0d23f56"
down_revision: str | Sequence[str] | None = "a7f3d9b12e45"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "omni_instances",
        sa.Column("company_id", sa.UUID(), nullable=False),
        sa.Column("omni_instance_id", sa.String(length=255), nullable=True),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("channel", sa.String(length=50), nullable=False),
        sa.Column("state", sa.String(length=20), nullable=False, server_default="connecting"),
        sa.Column("last_sync_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error", sa.String(length=500), nullable=True),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_omni_instances_omni_instance_id",
        "omni_instances",
        ["omni_instance_id"],
    )
    op.create_index("ix_omni_instances_state", "omni_instances", ["state"])
    op.create_index("ix_omni_instances_company_id", "omni_instances", ["company_id"])


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("ix_omni_instances_company_id", table_name="omni_instances")
    op.drop_index("ix_omni_instances_state", table_name="omni_instances")
    op.drop_index("ix_omni_instances_omni_instance_id", table_name="omni_instances")
    op.drop_table("omni_instances")
