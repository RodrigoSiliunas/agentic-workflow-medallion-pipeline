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

    async def get_pr_diff(self, pr_number: int) -> dict:
        """Retorna o diff de um PR especifico (arquivos alterados + patch)."""
        await self._ensure_credentials()
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(
                f"https://api.github.com/repos/{self._repo}/pulls/{pr_number}",
                headers=self._headers(),
            )
            resp.raise_for_status()
            pr = resp.json()

            files_resp = await client.get(
                f"https://api.github.com/repos/{self._repo}/pulls/{pr_number}/files",
                headers=self._headers(),
            )
            files_resp.raise_for_status()
            files = [
                {
                    "filename": f["filename"],
                    "status": f["status"],
                    "additions": f["additions"],
                    "deletions": f["deletions"],
                    "patch": f.get("patch", "")[:2000],
                }
                for f in files_resp.json()
            ]

            return {
                "number": pr["number"],
                "title": pr["title"],
                "state": pr["state"],
                "body": (pr.get("body") or "")[:1000],
                "files_changed": len(files),
                "files": files,
            }

    async def close_pull_request(self, pr_number: int) -> dict:
        """Fecha PR aberto no repositorio configurado."""
        await self._ensure_credentials()
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.patch(
                f"https://api.github.com/repos/{self._repo}/pulls/{pr_number}",
                json={"state": "closed"},
                headers=self._headers(),
            )
            resp.raise_for_status()
            pr = resp.json()
            logger.info(
                "github_pr_closed",
                company_id=str(self.company_id),
                pr_number=pr_number,
            )
            return {
                "pr_number": pr["number"],
                "pr_url": pr.get("html_url"),
                "state": pr.get("state"),
            }

    async def revert_merged_pr(self, pr_number: int) -> dict:
        """Cria commit de revert para PR mergeado e abre novo PR de rollback.

        Estrategia: obtém a tree do parent do merge commit (estado pré-PR)
        e cria um novo commit com essa tree sobre o HEAD atual do branch base.
        Isso produz um diff inverso equivalente a `git revert <merge_sha>`.
        """
        await self._ensure_credentials()
        async with httpx.AsyncClient(timeout=30) as client:
            # 1. Obter detalhes do PR original
            pr_resp = await client.get(
                f"https://api.github.com/repos/{self._repo}/pulls/{pr_number}",
                headers=self._headers(),
            )
            pr_resp.raise_for_status()
            pr_data = pr_resp.json()

            merge_sha = pr_data.get("merge_commit_sha")
            if not merge_sha:
                raise ValueError(f"PR #{pr_number} nao foi mergeado (sem merge_commit_sha)")

            base_branch = pr_data.get("base", {}).get("ref", "dev")

            # 2. Obter commit de merge para encontrar a tree pre-PR (pai do merge)
            commit_resp = await client.get(
                f"https://api.github.com/repos/{self._repo}/git/commits/{merge_sha}",
                headers=self._headers(),
            )
            commit_resp.raise_for_status()
            parents = commit_resp.json().get("parents", [])
            if not parents:
                raise ValueError(
                    f"Merge commit do PR #{pr_number} nao tem parents — nao e um merge commit"
                )

            pre_pr_sha = parents[0]["sha"]

            # 3. Obter tree SHA do estado pre-PR
            pre_pr_commit = await client.get(
                f"https://api.github.com/repos/{self._repo}/git/commits/{pre_pr_sha}",
                headers=self._headers(),
            )
            pre_pr_commit.raise_for_status()
            pre_pr_tree_sha = pre_pr_commit.json()["tree"]["sha"]

            # 4. Obter SHA atual do branch base
            ref_resp = await client.get(
                f"https://api.github.com/repos/{self._repo}/git/ref/heads/{base_branch}",
                headers=self._headers(),
            )
            ref_resp.raise_for_status()
            current_sha = ref_resp.json()["object"]["sha"]

            # 5. Criar commit de revert (tree pré-PR sobre HEAD atual)
            revert_commit_resp = await client.post(
                f"https://api.github.com/repos/{self._repo}/git/commits",
                json={
                    "message": (
                        f"revert: reverter PR #{pr_number} via Pipeline Editor rollback\n\n"
                        f"Reverts merge commit {merge_sha[:8]}"
                    ),
                    "tree": pre_pr_tree_sha,
                    "parents": [current_sha],
                },
                headers=self._headers(),
            )
            revert_commit_resp.raise_for_status()
            revert_sha = revert_commit_resp.json()["sha"]

            # 6. Criar branch de revert
            revert_branch = f"revert/pipeline-editor/{pr_number}"
            await client.post(
                f"https://api.github.com/repos/{self._repo}/git/refs",
                json={"ref": f"refs/heads/{revert_branch}", "sha": revert_sha},
                headers=self._headers(),
            )

            # 7. Abrir PR de revert
            revert_pr_resp = await client.post(
                f"https://api.github.com/repos/{self._repo}/pulls",
                json={
                    "title": f"revert: PR #{pr_number} — rollback Pipeline Editor",
                    "body": (
                        f"Revert automatico do PR #{pr_number} via Pipeline Editor.\n\n"
                        f"Merge commit revertido: `{merge_sha[:8]}`"
                    ),
                    "head": revert_branch,
                    "base": base_branch,
                },
                headers=self._headers(),
            )
            revert_pr_resp.raise_for_status()
            revert_pr = revert_pr_resp.json()

            logger.info(
                "github_revert_pr_created",
                company_id=str(self.company_id),
                original_pr=pr_number,
                revert_pr=revert_pr["number"],
            )
            return {
                "revert_pr_number": revert_pr["number"],
                "revert_pr_url": revert_pr["html_url"],
                "revert_branch": revert_branch,
                "original_pr_number": pr_number,
            }

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
