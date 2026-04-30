"""Service de custom LLM endpoints — CRUD + descoberta de models + test connection.

Discovery dual-mode:
- Tenta GET {base_url}/models (padrao OpenAI Chat Completions)
- Fallback GET {base_url_root}/api/tags (Ollama nativo)

Cifragem de api_key reutiliza EncryptionService (Fernet).

SSRF guard: `_validate_endpoint_url` aplicado em CRUD + discovery. Bloqueia
loopback/RFC1918/link-local salvo dev mode (ALLOW_LOOPBACK_LLM_ENDPOINTS).
Defesa contra api_key exfil: usuario que controla base_url poderia
apontar pro server dele e capturar a key + tokens — ngrok publicos ok,
internal hosts nao.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import httpx
import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.url_validator import UnsafeURLError, validate_public_url
from app.models.custom_llm_endpoint import CustomLLMEndpoint
from app.services.encryption import EncryptionService

logger = structlog.get_logger()


def _validate_endpoint_url(base_url: str) -> str:
    """Valida base_url + retorna URL normalizada. Raises ValueError em rejeicao."""
    try:
        return validate_public_url(
            base_url,
            allow_loopback=settings.ALLOW_LOOPBACK_LLM_ENDPOINTS,
        )
    except UnsafeURLError as exc:
        raise ValueError(f"base_url rejeitada por SSRF guard: {exc}") from exc


class CustomLLMService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.encryption = EncryptionService()

    async def list_for_company(self, company_id: uuid.UUID) -> list[CustomLLMEndpoint]:
        result = await self.db.execute(
            select(CustomLLMEndpoint)
            .where(CustomLLMEndpoint.company_id == company_id)
            .order_by(CustomLLMEndpoint.created_at.desc())
        )
        return list(result.scalars().all())

    async def get(
        self, company_id: uuid.UUID, endpoint_id: uuid.UUID
    ) -> CustomLLMEndpoint | None:
        result = await self.db.execute(
            select(CustomLLMEndpoint).where(
                CustomLLMEndpoint.id == endpoint_id,
                CustomLLMEndpoint.company_id == company_id,
            )
        )
        return result.scalar_one_or_none()

    async def create(
        self,
        company_id: uuid.UUID,
        name: str,
        base_url: str,
        api_key: str | None,
        models: list,
        enabled: bool = True,
    ) -> CustomLLMEndpoint:
        safe_url = _validate_endpoint_url(base_url)
        encrypted = self.encryption.encrypt(api_key) if api_key else None
        endpoint = CustomLLMEndpoint(
            company_id=company_id,
            name=name,
            base_url=safe_url,
            encrypted_api_key=encrypted,
            models=models or [],
            enabled=enabled,
        )
        self.db.add(endpoint)
        await self.db.flush()
        return endpoint

    async def update(
        self,
        endpoint: CustomLLMEndpoint,
        *,
        name: str | None = None,
        base_url: str | None = None,
        api_key: str | None = None,
        models: list | None = None,
        enabled: bool | None = None,
    ) -> CustomLLMEndpoint:
        if name is not None:
            endpoint.name = name
        if base_url is not None:
            endpoint.base_url = _validate_endpoint_url(base_url)
        if api_key is not None:
            # api_key string vazia = limpa. None = mantem.
            endpoint.encrypted_api_key = (
                self.encryption.encrypt(api_key) if api_key else None
            )
        if models is not None:
            endpoint.models = models
        if enabled is not None:
            endpoint.enabled = enabled
        await self.db.flush()
        return endpoint

    async def delete(self, endpoint: CustomLLMEndpoint) -> None:
        await self.db.delete(endpoint)
        await self.db.flush()

    def decrypt_api_key(self, endpoint: CustomLLMEndpoint) -> str:
        """Decifra api_key. Retorna 'ollama' dummy se nao tiver (Ollama default)."""
        if endpoint.encrypted_api_key:
            return self.encryption.decrypt(endpoint.encrypted_api_key)
        return "ollama"

    async def mark_tested(
        self,
        endpoint: CustomLLMEndpoint,
        success: bool,
        models: list | None = None,
    ) -> None:
        endpoint.last_tested_at = datetime.now(UTC)
        endpoint.last_test_status = "ok" if success else "failed"
        if success and models is not None:
            endpoint.models = models
        await self.db.flush()

    @staticmethod
    async def discover_models(
        base_url: str, api_key: str | None
    ) -> tuple[bool, list, str | None, str | None]:
        """Tenta descobrir models. Retorna (success, models, server_type, error).

        1. GET {base_url}/models (OpenAI standard)
        2. Fallback: extrai root da base_url e GET {root}/api/tags (Ollama nativo)
        """
        try:
            normalized = _validate_endpoint_url(base_url)
        except ValueError as exc:
            return False, [], None, str(exc)
        # Headers
        headers = {}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"

        async with httpx.AsyncClient(timeout=10.0) as client:
            # 1. OpenAI-compatible endpoint
            try:
                resp = await client.get(f"{normalized}/models", headers=headers)
                if resp.status_code == 200:
                    data = resp.json()
                    raw_models = data.get("data", []) if isinstance(data, dict) else data
                    models = [
                        {"id": m.get("id", ""), "label": m.get("id", "")}
                        for m in raw_models if isinstance(m, dict) and m.get("id")
                    ]
                    if models:
                        return True, models, "openai", None
            except httpx.HTTPError as exc:
                logger.debug("openai /models discovery failed", error=str(exc))

            # 2. Ollama fallback — strip /v1 suffix se tiver
            ollama_root = normalized.removesuffix("/v1")
            try:
                resp = await client.get(f"{ollama_root}/api/tags", headers=headers)
                if resp.status_code == 200:
                    data = resp.json()
                    raw_models = data.get("models", []) if isinstance(data, dict) else []
                    models = [
                        {"id": m.get("name", ""), "label": m.get("name", "")}
                        for m in raw_models if isinstance(m, dict) and m.get("name")
                    ]
                    if models:
                        return True, models, "ollama", None
            except httpx.HTTPError as exc:
                logger.debug("ollama /api/tags discovery failed", error=str(exc))

        return False, [], None, "Nenhum endpoint respondeu (/v1/models nem /api/tags)"
