"""Servico de gerenciamento de credenciais da empresa."""

import uuid
from datetime import UTC, datetime

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.credential import CompanyCredential
from app.services.encryption import EncryptionService

CREDENTIAL_TYPES = {
    "anthropic_api_key",
    "discord_bot_token",
    "telegram_bot_token",
    "github_token",
    "github_repo",
    "databricks_host",
    "databricks_token",
}


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
        token = await self.get_decrypted(company_id, "databricks_token")
        if not token:
            return {"success": False, "error": "Token Databricks nao configurado"}
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.get(
                    f"{host}/api/2.0/clusters/list",
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
