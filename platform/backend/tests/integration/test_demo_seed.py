"""Integration tests para seed_demo_tenant — valida idempotencia e shape."""

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.seed import (
    DEMO_ADMIN_EMAIL,
    DEMO_COMPANY_SLUG,
    DEMO_PIPELINE_NAME,
    DEMO_PIPELINE_TEMPLATE_SLUG,
    seed_demo_tenant,
)
from app.models.company import Company
from app.models.pipeline import Pipeline
from app.models.user import User

pytestmark = pytest.mark.asyncio


async def test_seed_demo_tenant_creates_company_admin_pipeline(db_session: AsyncSession):
    await seed_demo_tenant(db_session)

    company = (
        await db_session.execute(
            select(Company).where(Company.slug == DEMO_COMPANY_SLUG)
        )
    ).scalar_one()

    admin = (
        await db_session.execute(
            select(User).where(
                User.company_id == company.id,
                User.email == DEMO_ADMIN_EMAIL,
            )
        )
    ).scalar_one()
    assert admin.role == "admin"  # admin inclui chat + create_pr

    pipeline = (
        await db_session.execute(
            select(Pipeline).where(
                Pipeline.company_id == company.id,
                Pipeline.name == DEMO_PIPELINE_NAME,
            )
        )
    ).scalar_one()
    assert pipeline.github_repo == "RodrigoSiliunas/agentic-workflow-medallion-pipeline"
    assert pipeline.config == {"template_slug": DEMO_PIPELINE_TEMPLATE_SLUG}


async def test_seed_demo_tenant_is_idempotent(db_session: AsyncSession):
    # Roda 3x — nao deve duplicar company/admin/pipeline
    await seed_demo_tenant(db_session)
    await seed_demo_tenant(db_session)
    await seed_demo_tenant(db_session)

    companies = (
        await db_session.execute(
            select(Company).where(Company.slug == DEMO_COMPANY_SLUG)
        )
    ).scalars().all()
    assert len(companies) == 1

    admins = (
        await db_session.execute(
            select(User).where(User.email == DEMO_ADMIN_EMAIL)
        )
    ).scalars().all()
    assert len(admins) == 1

    pipelines = (
        await db_session.execute(
            select(Pipeline).where(Pipeline.name == DEMO_PIPELINE_NAME)
        )
    ).scalars().all()
    assert len(pipelines) == 1
