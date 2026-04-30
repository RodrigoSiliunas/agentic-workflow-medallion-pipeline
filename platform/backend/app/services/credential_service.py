"""Servico de gerenciamento de credenciais da empresa."""

import uuid
from datetime import UTC, datetime

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.url_validator import UnsafeURLError, validate_databricks_workspace_host
from app.models.credential import CompanyCredential
from app.services.encryption import EncryptionService

CREDENTIAL_TYPES = {
    # LLM providers (multi-provider — configura uma ou mais)
    "anthropic_api_key",
    "openai_api_key",
    "google_api_key",
    # Channels (Omni-managed)
    "discord_bot_token",
    "telegram_bot_token",
    # GitHub
    "github_token",
    "github_repo",
    # Databricks workspace-level
    "databricks_host",
    "databricks_token",
    # Account API OAuth M2M — usado pra criar workspace/network/storage configs
    # via /api/2.0/accounts/{id}/... endpoints (workspace customer-managed VPC).
    "databricks_account_id",
    "databricks_oauth_client_id",
    "databricks_oauth_secret",
    # AWS — credenciais que o saga usa pra Terraform/boto3
    "aws_access_key_id",
    "aws_secret_access_key",
    "aws_region",
}

# Mapeamento provider -> credential type (orchestrator usa pra resolver api_key)
PROVIDER_CREDENTIAL_MAP = {
    "anthropic": "anthropic_api_key",
    "openai": "openai_api_key",
    "google": "google_api_key",
}

# Credenciais que o wizard pode pre-preencher/sobrescrever por deploy.
# Mantido em ordem pra frontend saber o que mostrar.
DEPLOY_CREDENTIAL_TYPES = (
    "aws_access_key_id",
    "aws_secret_access_key",
    "aws_region",
    "databricks_host",
    "databricks_token",
    "github_token",
)


class CredentialService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.encryption = EncryptionService()

    async def get_all(self, company_id: uuid.UUID) -> dict[str, dict]:
        """Retorna todas as credenciais da empresa (sem valores decriptados)."""
        result = await self.db.execute(
            select(CompanyCredential).where(CompanyCredential.company_id == company_id)
        )
        creds = result.scalars().all()
        return {
            c.credential_type: {
                "is_configured": True,
                "is_valid": c.is_valid,
                "last_tested_at": c.last_tested_at.isoformat() if c.last_tested_at else None,
            }
            for c in creds
        }

    async def set_credential(
        self, company_id: uuid.UUID, credential_type: str, value: str
    ) -> CompanyCredential:
        """Salva ou atualiza uma credencial (criptografada)."""
        if credential_type not in CREDENTIAL_TYPES:
            raise ValueError(f"Tipo invalido: {credential_type}")

        # SSRF guard: rejeitar databricks_host fora do allowlist na escrita.
        # Defense-in-depth — validacao tambem ocorre no momento de uso.
        if credential_type == "databricks_host":
            try:
                value = validate_databricks_workspace_host(value)
            except UnsafeURLError as exc:
                raise ValueError(f"databricks_host invalido: {exc}") from exc

        encrypted = self.encryption.encrypt(value)

        result = await self.db.execute(
            select(CompanyCredential).where(
                CompanyCredential.company_id == company_id,
                CompanyCredential.credential_type == credential_type,
            )
        )
        cred = result.scalar_one_or_none()

        if cred:
            cred.encrypted_value = encrypted
            cred.is_valid = False
            cred.last_tested_at = None
        else:
            cred = CompanyCredential(
                company_id=company_id,
                credential_type=credential_type,
                encrypted_value=encrypted,
            )
            self.db.add(cred)

        await self.db.flush()
        return cred

    async def get_decrypted(self, company_id: uuid.UUID, credential_type: str) -> str | None:
        """Retorna valor decriptado (uso interno, nunca expor via API)."""
        result = await self.db.execute(
            select(CompanyCredential).where(
                CompanyCredential.company_id == company_id,
                CompanyCredential.credential_type == credential_type,
            )
        )
        cred = result.scalar_one_or_none()
        if not cred:
            return None
        return self.encryption.decrypt(cred.encrypted_value)

    async def get_all_decrypted(self, company_id: uuid.UUID) -> dict[str, str]:
        """Retorna TODAS as credenciais decriptadas da empresa em 1 query.

        Uso interno para o POST /deployments — evita N queries sequenciais.
        """
        result = await self.db.execute(
            select(CompanyCredential).where(CompanyCredential.company_id == company_id)
        )
        creds = result.scalars().all()
        return {
            c.credential_type: self.encryption.decrypt(c.encrypted_value)
            for c in creds
        }

    async def test_credential(
        self, company_id: uuid.UUID, credential_type: str
    ) -> dict:
        """Testa se a credencial funciona."""
        value = await self.get_decrypted(company_id, credential_type)
        if not value:
            return {"success": False, "error": "Credencial nao configurada"}

        testers = {
            "anthropic_api_key": self._test_anthropic,
            "databricks_host": self._test_databricks,
            "github_token": self._test_github,
        }

        tester = testers.get(credential_type)
        if not tester:
            # Credenciais sem teste automatico (tokens de canal)
            return {"success": True, "message": "Sem validacao automatica"}

        result = await tester(company_id, value)

        # Atualizar status no DB
        db_result = await self.db.execute(
            select(CompanyCredential).where(
                CompanyCredential.company_id == company_id,
                CompanyCredential.credential_type == credential_type,
            )
        )
        cred = db_result.scalar_one_or_none()
        if cred:
            cred.is_valid = result["success"]
            cred.last_tested_at = datetime.now(UTC)
            await self.db.flush()

        return result

    async def _test_anthropic(self, company_id: uuid.UUID, api_key: str) -> dict:
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.get(
                    "https://api.anthropic.com/v1/models",
                    headers={
                        "x-api-key": api_key,
                        "anthropic-version": "2023-06-01",
                    },
                    timeout=10,
                )
                if resp.status_code == 200:
                    return {"success": True, "message": "Anthropic API key valida"}
                return {"success": False, "error": f"HTTP {resp.status_code}"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def _test_databricks(self, company_id: uuid.UUID, host: str) -> dict:
        try:
            safe_host = validate_databricks_workspace_host(host)
        except UnsafeURLError as exc:
            return {"success": False, "error": str(exc)}
        token = await self.get_decrypted(company_id, "databricks_token")
        if not token:
            return {"success": False, "error": "Token Databricks nao configurado"}
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.get(
                    f"{safe_host}/api/2.0/clusters/list",
                    headers={"Authorization": f"Bearer {token}"},
                    timeout=10,
                )
                if resp.status_code in (200, 403):
                    return {"success": True, "message": "Conexao Databricks OK"}
                return {"success": False, "error": f"HTTP {resp.status_code}"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def _test_github(self, company_id: uuid.UUID, token: str) -> dict:
        repo = await self.get_decrypted(company_id, "github_repo")
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.get(
                    f"https://api.github.com/repos/{repo}" if repo else "https://api.github.com/user",
                    headers={"Authorization": f"Bearer {token}"},
                    timeout=10,
                )
                if resp.status_code == 200:
                    return {"success": True, "message": "GitHub token valido"}
                return {"success": False, "error": f"HTTP {resp.status_code}"}
        except Exception as e:
            return {"success": False, "error": str(e)}
