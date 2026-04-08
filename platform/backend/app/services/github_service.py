"""Servico de integracao com GitHub — usa credenciais da empresa."""

import uuid

import httpx
import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.credential_service import CredentialService

logger = structlog.get_logger()


class GitHubService:
    def __init__(self, db: AsyncSession, company_id: uuid.UUID):
        self.db = db
        self.company_id = company_id
        self._cred_service = CredentialService(db)
        self._token: str | None = None
        self._repo: str | None = None

    async def _ensure_credentials(self):
        if not self._token:
            self._token = await self._cred_service.get_decrypted(
                self.company_id, "github_token"
            )
            self._repo = await self._cred_service.get_decrypted(
                self.company_id, "github_repo"
            )
        if not self._token:
            raise ValueError("GitHub nao configurado para esta empresa")

    def _headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self._token}",
            "Accept": "application/vnd.github.v3+json",
        }

    async def read_file(self, path: str, ref: str = "main") -> str:
        """Le conteudo de um arquivo do repositorio."""
        await self._ensure_credentials()
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(
                f"https://api.github.com/repos/{self._repo}/contents/{path}",
                params={"ref": ref},
                headers=self._headers(),
            )
            resp.raise_for_status()
            data = resp.json()
            import base64
            return base64.b64decode(data["content"]).decode("utf-8")

    async def list_recent_prs(self, state: str = "all", limit: int = 10) -> list[dict]:
        """Lista PRs recentes do repositorio."""
        await self._ensure_credentials()
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(
                f"https://api.github.com/repos/{self._repo}/pulls",
                params={"state": state, "per_page": limit, "sort": "updated"},
                headers=self._headers(),
            )
            resp.raise_for_status()
            return [
                {
                    "number": pr["number"],
                    "title": pr["title"],
                    "state": pr["state"],
                    "url": pr["html_url"],
                    "author": pr["user"]["login"],
                    "created_at": pr["created_at"],
                    "updated_at": pr["updated_at"],
                }
                for pr in resp.json()
            ]

    async def create_pr(
        self, title: str, body: str, branch: str,
        base: str = "dev", files: dict[str, str] | None = None
    ) -> dict:
        """Cria branch, commita arquivos, e abre PR."""
        await self._ensure_credentials()
        async with httpx.AsyncClient(timeout=30) as client:
            # Obter SHA do base
            ref_resp = await client.get(
                f"https://api.github.com/repos/{self._repo}/git/ref/heads/{base}",
                headers=self._headers(),
            )
            ref_resp.raise_for_status()
            base_sha = ref_resp.json()["object"]["sha"]

            # Criar branch
            await client.post(
                f"https://api.github.com/repos/{self._repo}/git/refs",
                json={"ref": f"refs/heads/{branch}", "sha": base_sha},
                headers=self._headers(),
            )

            # Commitar arquivos
            if files:
                for path, content in files.items():
                    # Verificar se arquivo existe
                    try:
                        existing = await client.get(
                            f"https://api.github.com/repos/{self._repo}/contents/{path}",
                            params={"ref": branch},
                            headers=self._headers(),
                        )
                        sha = existing.json().get("sha") if existing.status_code == 200 else None
                    except Exception:
                        sha = None

                    import base64
                    payload = {
                        "message": f"fix: {title}",
                        "content": base64.b64encode(content.encode()).decode(),
                        "branch": branch,
                    }
                    if sha:
                        payload["sha"] = sha

                    await client.put(
                        f"https://api.github.com/repos/{self._repo}/contents/{path}",
                        json=payload,
                        headers=self._headers(),
                    )

            # Criar PR
            pr_resp = await client.post(
                f"https://api.github.com/repos/{self._repo}/pulls",
                json={"title": title, "body": body, "head": branch, "base": base},
                headers=self._headers(),
            )
            pr_resp.raise_for_status()
            pr = pr_resp.json()

            return {
                "pr_number": pr["number"],
                "pr_url": pr["html_url"],
                "branch": branch,
            }
