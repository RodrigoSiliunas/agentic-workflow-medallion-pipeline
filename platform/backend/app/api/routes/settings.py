"""Settings routes — credenciais da empresa, model selection."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import AuthContext, require_permission
from app.database.session import get_db
from app.models.company import Company
from app.schemas.settings import (
    CompanySettingsResponse,
    CredentialSetRequest,
    TestCredentialResponse,
    UpdatePreferredModelRequest,
)
from app.services.credential_service import CredentialService

router = APIRouter()


@router.get("", response_model=CompanySettingsResponse)
async def get_settings(
    auth: AuthContext = Depends(require_permission("manage_settings")),
    db: AsyncSession = Depends(get_db),
):
    """Retorna settings da empresa (credenciais sem valores, apenas status)."""
    service = CredentialService(db)
    credentials = await service.get_all(auth.company_id)

    result = await db.execute(select(Company).where(Company.id == auth.company_id))
    company = result.scalar_one()

    return CompanySettingsResponse(
        preferred_model=company.preferred_model,
        credentials=credentials,
    )


@router.put("/credentials")
async def set_credential(
    data: CredentialSetRequest,
    auth: AuthContext = Depends(require_permission("manage_credentials")),
    db: AsyncSession = Depends(get_db),
):
    """Salva uma credencial (criptografada)."""
    service = CredentialService(db)
    try:
        await service.set_credential(auth.company_id, data.credential_type, data.value)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e)
        ) from e
    return {"status": "saved", "credential_type": data.credential_type}


@router.post("/credentials/{credential_type}/test", response_model=TestCredentialResponse)
async def test_credential(
    credential_type: str,
    auth: AuthContext = Depends(require_permission("manage_credentials")),
    db: AsyncSession = Depends(get_db),
):
    """Testa se a credencial funciona (Anthropic, Databricks, GitHub)."""
    service = CredentialService(db)
    result = await service.test_credential(auth.company_id, credential_type)
    return TestCredentialResponse(**result)


@router.put("/preferred-model")
async def update_preferred_model(
    data: UpdatePreferredModelRequest,
    auth: AuthContext = Depends(require_permission("manage_settings")),
    db: AsyncSession = Depends(get_db),
):
    """Atualiza modelo LLM preferido da empresa (sonnet/opus)."""
    if data.model not in ("sonnet", "opus"):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Modelo deve ser 'sonnet' ou 'opus'",
        )

    result = await db.execute(select(Company).where(Company.id == auth.company_id))
    company = result.scalar_one()
    company.preferred_model = data.model
    await db.flush()

    return {"status": "updated", "preferred_model": data.model}
