"""Settings routes — credenciais da empresa, model selection."""

import uuid

import httpx
import structlog
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

logger = structlog.get_logger()

# Mapeamento: credential_type da plataforma → secret key no Databricks
_DATABRICKS_SECRET_MAP = {
    "anthropic_api_key": "anthropic-api-key",
    "github_token": "github-token",
    "aws_access_key_id": "aws-access-key-id",
    "aws_secret_access_key": "aws-secret-access-key",
    "aws_region": "aws-region",
}
_DATABRICKS_SCOPE = "medallion-pipeline"


async def _sync_to_databricks_secrets(
    service: CredentialService, company_id: uuid.UUID,
    credential_type: str, value: str,
) -> None:
    """Sincroniza credencial com Databricks Secrets (se Databricks configurado)."""
    secret_key = _DATABRICKS_SECRET_MAP.get(credential_type)
    if not secret_key:
        return
    try:
        host = await service.get_decrypted(company_id, "databricks_host")
        token = await service.get_decrypted(company_id, "databricks_token")
        if not host or not token:
            return
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(
                f"{host}/api/2.0/secrets/put",
                json={"scope": _DATABRICKS_SCOPE, "key": secret_key, "string_value": value},
                headers={"Authorization": f"Bearer {token}"},
            )
            if resp.status_code == 200:
                logger.info("Databricks secret synced", key=secret_key)
            else:
                logger.warning(
                    "Databricks secret sync failed", key=secret_key, status=resp.status_code,
                )
    except Exception as exc:
        logger.warning("Databricks secret sync error", key=secret_key, error=str(exc))

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
        preferred_provider=company.preferred_provider,
        credentials=credentials,
    )


@router.put("/credentials")
async def set_credential(
    data: CredentialSetRequest,
    auth: AuthContext = Depends(require_permission("manage_credentials")),
    db: AsyncSession = Depends(get_db),
):
    """Salva uma credencial (criptografada). Sincroniza com Databricks Secrets."""
    service = CredentialService(db)
    try:
        await service.set_credential(auth.company_id, data.credential_type, data.value)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e)
        ) from e

    # Sincronizar com Databricks Secrets se aplicavel
    await _sync_to_databricks_secrets(service, auth.company_id, data.credential_type, data.value)

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


_VALID_PROVIDERS = {"anthropic", "openai", "google"}


@router.put("/preferred-model")
async def update_preferred_model(
    data: UpdatePreferredModelRequest,
    auth: AuthContext = Depends(require_permission("manage_settings")),
    db: AsyncSession = Depends(get_db),
):
    """Atualiza model LLM preferido da empresa.

    Aceita qualquer string (model IDs novos: claude-opus-4-7, gpt-5,
    gemini-2.5-pro, etc). Validacao de combinacao provider/model fica
    no orchestrator (factory raises se model nao existir no provider).
    """
    if not data.model or len(data.model) > 100:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Model id invalido",
        )

    result = await db.execute(select(Company).where(Company.id == auth.company_id))
    company = result.scalar_one()
    company.preferred_model = data.model
    await db.flush()

    return {"status": "updated", "preferred_model": data.model}


@router.put("/preferred-provider")
async def update_preferred_provider(
    data: dict,
    auth: AuthContext = Depends(require_permission("manage_settings")),
    db: AsyncSession = Depends(get_db),
):
    """Atualiza provider LLM padrao da empresa (anthropic/openai/google)."""
    provider = data.get("provider", "")
    if provider not in _VALID_PROVIDERS:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Provider deve ser um de: {sorted(_VALID_PROVIDERS)}",
        )
    result = await db.execute(select(Company).where(Company.id == auth.company_id))
    company = result.scalar_one()
    company.preferred_provider = provider
    await db.flush()
    return {"status": "updated", "preferred_provider": provider}
