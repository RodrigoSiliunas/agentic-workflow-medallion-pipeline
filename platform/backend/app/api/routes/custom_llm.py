"""Routes pra custom LLM endpoints (Ollama, vLLM, OpenRouter, etc).

CRUD completo + test connection + auto-discovery de models.
"""

from __future__ import annotations

import uuid

import structlog
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import AuthContext, get_current_user, require_permission
from app.database.session import get_db
from app.schemas.custom_llm import (
    CustomLLMEndpointCreate,
    CustomLLMEndpointResponse,
    CustomLLMEndpointUpdate,
    TestEndpointRequest,
    TestEndpointResponse,
)
from app.services.custom_llm_service import CustomLLMService

logger = structlog.get_logger()
router = APIRouter()


def _serialize(endpoint) -> dict:
    return {
        "id": str(endpoint.id),
        "name": endpoint.name,
        "base_url": endpoint.base_url,
        "has_api_key": endpoint.encrypted_api_key is not None,
        "models": endpoint.models or [],
        "enabled": endpoint.enabled,
        "last_tested_at": endpoint.last_tested_at,
        "last_test_status": endpoint.last_test_status,
        "created_at": endpoint.created_at,
        "updated_at": endpoint.updated_at,
    }


@router.get("", response_model=list[CustomLLMEndpointResponse])
async def list_endpoints(
    auth: AuthContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    svc = CustomLLMService(db)
    endpoints = await svc.list_for_company(auth.company_id)
    return [_serialize(e) for e in endpoints]


@router.post("", response_model=CustomLLMEndpointResponse, status_code=201)
async def create_endpoint(
    data: CustomLLMEndpointCreate,
    auth: AuthContext = Depends(require_permission("manage_credentials")),
    db: AsyncSession = Depends(get_db),
):
    svc = CustomLLMService(db)
    try:
        endpoint = await svc.create(
            company_id=auth.company_id,
            name=data.name,
            base_url=data.base_url,
            api_key=data.api_key,
            models=[m.model_dump() for m in data.models],
            enabled=data.enabled,
        )
        await db.commit()
    except Exception as exc:
        await db.rollback()
        # Provavel UniqueConstraint violation
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Erro ao criar endpoint: {exc}",
        ) from exc
    return _serialize(endpoint)


@router.put("/{endpoint_id}", response_model=CustomLLMEndpointResponse)
async def update_endpoint(
    endpoint_id: uuid.UUID,
    data: CustomLLMEndpointUpdate,
    auth: AuthContext = Depends(require_permission("manage_credentials")),
    db: AsyncSession = Depends(get_db),
):
    svc = CustomLLMService(db)
    endpoint = await svc.get(auth.company_id, endpoint_id)
    if not endpoint:
        raise HTTPException(status_code=404, detail="Endpoint nao encontrado")
    await svc.update(
        endpoint,
        name=data.name,
        base_url=data.base_url,
        api_key=data.api_key,
        models=[m.model_dump() for m in data.models] if data.models is not None else None,
        enabled=data.enabled,
    )
    await db.commit()
    return _serialize(endpoint)


@router.delete("/{endpoint_id}", status_code=204)
async def delete_endpoint(
    endpoint_id: uuid.UUID,
    auth: AuthContext = Depends(require_permission("manage_credentials")),
    db: AsyncSession = Depends(get_db),
):
    svc = CustomLLMService(db)
    endpoint = await svc.get(auth.company_id, endpoint_id)
    if not endpoint:
        raise HTTPException(status_code=404, detail="Endpoint nao encontrado")
    await svc.delete(endpoint)
    await db.commit()


@router.post("/test", response_model=TestEndpointResponse)
async def test_endpoint_connection(
    data: TestEndpointRequest,
    auth: AuthContext = Depends(require_permission("manage_credentials")),
    db: AsyncSession = Depends(get_db),
):
    """Testa conexao + descobre models. Body com base_url + api_key opcional."""
    success, models, server_type, error = await CustomLLMService.discover_models(
        data.base_url, data.api_key
    )
    return TestEndpointResponse(
        success=success,
        error=error,
        discovered_models=models,
        server_type=server_type,
    )


@router.post("/{endpoint_id}/refresh-models", response_model=CustomLLMEndpointResponse)
async def refresh_models(
    endpoint_id: uuid.UUID,
    auth: AuthContext = Depends(require_permission("manage_credentials")),
    db: AsyncSession = Depends(get_db),
):
    """Re-descobre models do endpoint salvo + atualiza no DB."""
    svc = CustomLLMService(db)
    endpoint = await svc.get(auth.company_id, endpoint_id)
    if not endpoint:
        raise HTTPException(status_code=404, detail="Endpoint nao encontrado")

    api_key = svc.decrypt_api_key(endpoint)
    success, models, _, _ = await CustomLLMService.discover_models(
        endpoint.base_url, api_key
    )
    await svc.mark_tested(endpoint, success=success, models=models if success else None)
    await db.commit()
    return _serialize(endpoint)
