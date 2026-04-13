"""Servico de integracao com Databricks — usa credenciais da empresa."""

import uuid

import httpx
import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.credential_service import CredentialService

logger = structlog.get_logger()


class DatabricksService:
    def __init__(self, db: AsyncSession, company_id: uuid.UUID):
        self.db = db
        self.company_id = company_id
        self._cred_service = CredentialService(db)
        self._host: str | None = None
        self._token: str | None = None

    async def _ensure_credentials(self):
        if not self._host:
            self._host = await self._cred_service.get_decrypted(
                self.company_id, "databricks_host"
            )
            self._token = await self._cred_service.get_decrypted(
                self.company_id, "databricks_token"
            )
        if not self._host or not self._token:
            raise ValueError("Databricks nao configurado para esta empresa")

    def _headers(self) -> dict:
        return {"Authorization": f"Bearer {self._token}"}

    async def list_jobs(self, limit: int = 20) -> list[dict]:
        """Lista jobs/workflows do workspace Databricks."""
        await self._ensure_credentials()
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(
                f"{self._host}/api/2.1/jobs/list",
                params={"limit": limit},
                headers=self._headers(),
            )
            resp.raise_for_status()
            jobs = resp.json().get("jobs", [])
            return [
                {
                    "job_id": j.get("job_id"),
                    "name": j.get("settings", {}).get("name", ""),
                    "created_time": j.get("created_time"),
                    "creator": j.get("creator_user_name", ""),
                }
                for j in jobs
            ]

    async def get_job_status(self, job_id: int) -> dict:
        """Retorna status do job Databricks."""
        await self._ensure_credentials()
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(
                f"{self._host}/api/2.1/jobs/get",
                params={"job_id": job_id},
                headers=self._headers(),
            )
            resp.raise_for_status()
            return resp.json()

    async def list_runs(self, job_id: int, limit: int = 10) -> list[dict]:
        """Lista ultimas runs do job."""
        await self._ensure_credentials()
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(
                f"{self._host}/api/2.1/jobs/runs/list",
                params={"job_id": job_id, "limit": limit},
                headers=self._headers(),
            )
            resp.raise_for_status()
            return resp.json().get("runs", [])

    async def get_run_output(self, run_id: int) -> dict:
        """Retorna output/logs de uma run."""
        await self._ensure_credentials()
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(
                f"{self._host}/api/2.1/jobs/runs/get-output",
                params={"run_id": run_id},
                headers=self._headers(),
            )
            resp.raise_for_status()
            return resp.json()

    async def query_table(self, sql: str, max_rows: int = 100) -> dict:
        """Executa query SQL via Databricks SQL Statement API."""
        await self._ensure_credentials()
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                f"{self._host}/api/2.0/sql/statements",
                json={
                    "statement": sql,
                    "warehouse_id": "auto",
                    "wait_timeout": "30s",
                    "row_limit": max_rows,
                },
                headers=self._headers(),
            )
            resp.raise_for_status()
            return resp.json()

    async def trigger_run(self, job_id: int) -> dict:
        """Dispara execucao manual do job."""
        await self._ensure_credentials()
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(
                f"{self._host}/api/2.1/jobs/run-now",
                json={"job_id": job_id},
                headers=self._headers(),
            )
            resp.raise_for_status()
            return resp.json()

    async def get_table_schemas(self, catalog: str = "medallion") -> list[dict]:
        """Lista schemas das tabelas via Unity Catalog."""
        await self._ensure_credentials()
        schemas = []
        for schema_name in ["bronze", "silver", "gold"]:
            try:
                async with httpx.AsyncClient(timeout=15) as client:
                    resp = await client.get(
                        f"{self._host}/api/2.1/unity-catalog/tables",
                        params={"catalog_name": catalog, "schema_name": schema_name},
                        headers=self._headers(),
                    )
                    if resp.status_code == 200:
                        for table in resp.json().get("tables", []):
                            schemas.append({
                                "catalog": catalog,
                                "schema": schema_name,
                                "table": table["name"],
                                "columns": [
                                    {"name": c["name"], "type": c["type_name"]}
                                    for c in table.get("columns", [])
                                ],
                            })
            except Exception as e:
                logger.warning("Erro ao listar schemas", schema=schema_name, error=str(e))
        return schemas

    async def get_pipeline_summary(self, job_id: int) -> dict:
        """Resumo completo do pipeline (para Context Engine nivel 1).

        Timestamps sao convertidos de milissegundos Unix pra ISO string
        legivel (timezone America/Sao_Paulo) pra evitar que o LLM erre
        a conversao.
        """
        try:
            runs = await self.list_runs(job_id, limit=1)
            latest = runs[0] if runs else None

            return {
                "status": (
                    latest.get("state", {}).get("result_state", "UNKNOWN")
                    if latest else "NO_RUNS"
                ),
                "last_run_at": _ms_to_iso(latest.get("start_time")) if latest else None,
                "duration_sec": (latest.get("run_duration", 0) / 1000) if latest else 0,
                "tasks": {
                    t["task_key"]: t.get("state", {}).get("result_state", "UNKNOWN")
                    for t in (latest.get("tasks") or [])
                } if latest else {},
            }
        except Exception as e:
            logger.error("Erro ao obter resumo do pipeline", error=str(e))
            return {"status": "ERROR", "error": str(e)}


def _ms_to_iso(ms: int | None) -> str | None:
    """Converte timestamp Databricks (milissegundos Unix) pra ISO string SP."""
    if not ms:
        return None
    from datetime import datetime, timedelta, timezone

    dt = datetime.fromtimestamp(ms / 1000, tz=timezone(timedelta(hours=-3)))
    return dt.strftime("%Y-%m-%d %H:%M:%S (horario de Brasilia)")
