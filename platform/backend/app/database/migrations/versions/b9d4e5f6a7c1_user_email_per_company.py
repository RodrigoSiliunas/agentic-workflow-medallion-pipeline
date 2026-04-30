"""user_email_per_company

Troca o unique constraint global em users.email por composto
(company_id, email). Evita squat de email cross-tenant — atacante em
empresa X nao bloqueia mais empresa Y de cadastrar mesmo email.

Login passa a aceitar company_slug opcional pra desambiguar quando
mesmo email existe em multiplas empresas.

Revision ID: b9d4e5f6a7c1
Revises: f1a2b3c4d5e6
Create Date: 2026-04-29 14:00:00.000000

"""
from typing import Sequence, Union

from alembic import op


revision: str = "b9d4e5f6a7c1"
down_revision: Union[str, Sequence[str], None] = "f1a2b3c4d5e6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Drop old global unique. Nome gerado pelo Postgres em initial_schema:
    # users_email_key (default convention pro UniqueConstraint sem name).
    op.drop_constraint("users_email_key", "users", type_="unique")
    # Index pra speed em login lookups (where email = X)
    op.create_index("ix_users_email", "users", ["email"], unique=False)
    # Composite unique — email so unico DENTRO da empresa
    op.create_unique_constraint(
        "uq_users_company_email", "users", ["company_id", "email"]
    )


def downgrade() -> None:
    op.drop_constraint("uq_users_company_email", "users", type_="unique")
    op.drop_index("ix_users_email", table_name="users")
    op.create_unique_constraint("users_email_key", "users", ["email"])
