"""Servico de integracao com Databricks — usa credenciais da empresa.

T7 Phase 4: `httpx.AsyncClient` compartilhado (singleton classmethod) em
vez de criar um por request. Segue o padrão de `OmniService._client()`.
Connection pooling reaproveita sockets; latency de request subsequente
cai do cold-start do TCP handshake.
"""

import asyncio
import uuid

import httpx
import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.url_validator import UnsafeURLError, validate_databricks_workspace_host
from app.services.credential_service import CredentialService

logger = structlog.get_logger()


class DatabricksService:
    # Cliente httpx compartilhado entre todas instancias — pool de
    # conexoes reutilizado. Fechado no lifespan shutdown via `close()`.
    _shared_client: httpx.AsyncClient | None = None

    def __init__(self, db: AsyncSession, company_id: uuid.UUID):
        self.db = db
        self.company_id = company_id
        self._cred_service = CredentialService(db)
        self._host: str | None = None
        self._token: str | None = None
        # Cache do warehouse ID resolvido lazy na primeira query_table.
        # Evita listar warehouses N vezes; reseta quando credenciais mudam.
        self._warehouse_id: str | None = None

    @classmethod
    def _client(cls) -> httpx.AsyncClient:
        if cls._shared_client is None:
            cls._shared_client = httpx.AsyncClient(
                timeout=httpx.Timeout(connect=5.0, read=15.0, write=10.0, pool=5.0),
                limits=httpx.Limits(max_keepalive_connections=10, max_connections=20),
            )
        return cls._shared_client

    @classmethod
    async def close(cls) -> None:
        if cls._shared_client:
            await cls._shared_client.aclose()
            cls._shared_client = None

    async def _ensure_credentials(self):
        if not self._host:
            raw_host = await self._cred_service.get_decrypted(
                self.company_id, "databricks_host"
            )
            self._token = await self._cred_service.get_decrypted(
                self.company_id, "databricks_token"
            )
            if raw_host:
                try:
                    self._host = validate_databricks_workspace_host(raw_host)
                except UnsafeURLError as exc:
                    raise ValueError(
                        f"databricks_host invalido para esta empresa: {exc}"
                    ) from exc
        if not self._host or not self._token:
            raise ValueError("Databricks nao configurado para esta empresa")

    def _headers(self) -> dict:
        return {"Authorization": f"Bearer {self._token}"}

    async def list_jobs(self, limit: int = 20) -> list[dict]:
        """Lista jobs/workflows do workspace Databricks."""
        await self._ensure_credentials()
        resp = await self._client().get(
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

    async def get_job_details(self, job_id: int) -> dict:
        """Retorna configuracao completa do job (schedule, cluster, tasks, etc)."""
        await self._ensure_credentials()
        resp = await self._client().get(
            f"{self._host}/api/2.1/jobs/get",
            params={"job_id": job_id},
            headers=self._headers(),
        )
        resp.raise_for_status()
        data = resp.json()
        settings = data.get("settings", {})
        schedule = settings.get("schedule", {})
        return {
            "job_id": data.get("job_id"),
            "name": settings.get("name", ""),
            "schedule": {
                "cron": schedule.get("quartz_cron_expression", "sem agendamento"),
                "timezone": schedule.get("timezone_id", "UTC"),
                "paused": schedule.get("pause_status", "UNPAUSED"),
            },
            "tasks": [
                {"task_key": t.get("task_key"), "description": t.get("description", "")}
                for t in settings.get("tasks", [])
            ],
            "max_concurrent_runs": settings.get("max_concurrent_runs", 1),
            "timeout_seconds": settings.get("timeout_seconds", 0),
            "tags": settings.get("tags", {}),
            "creator": data.get("creator_user_name", ""),
        }

    async def update_job_schedule(
        self, job_id: int, cron: str, timezone: str = "America/Sao_Paulo",
        paused: bool = False,
    ) -> dict:
        """Altera o agendamento (cron) de um job Databricks."""
        await self._ensure_credentials()
        payload = {
            "job_id": job_id,
            "new_settings": {
                "schedule": {
                    "quartz_cron_expression": cron,
                    "timezone_id": timezone,
                    "pause_status": "PAUSED" if paused else "UNPAUSED",
                },
            },
        }
        resp = await self._client().post(
            f"{self._host}/api/2.1/jobs/update",
            json=payload,
            headers=self._headers(),
        )
        resp.raise_for_status()
        return {"status": "updated", "job_id": job_id, "new_cron": cron, "timezone": timezone}

    async def update_job_settings(
        self, job_id: int, settings: dict,
    ) -> dict:
        """Atualiza configuracoes arbitrarias de um job."""
        await self._ensure_credentials()
        resp = await self._client().post(
            f"{self._host}/api/2.1/jobs/update",
            json={"job_id": job_id, "new_settings": settings},
            headers=self._headers(),
        )
        resp.raise_for_status()
        changed = list(settings.keys())
        return {"status": "updated", "job_id": job_id, "settings_changed": changed}

    async def get_job_status(self, job_id: int) -> dict:
        """Retorna status do job Databricks."""
        await self._ensure_credentials()
        resp = await self._client().get(
            f"{self._host}/api/2.1/jobs/get",
            params={"job_id": job_id},
            headers=self._headers(),
        )
        resp.raise_for_status()
        return resp.json()

    async def list_runs(self, job_id: int, limit: int = 10) -> list[dict]:
        """Lista ultimas runs do job."""
        await self._ensure_credentials()
        resp = await self._client().get(
            f"{self._host}/api/2.1/jobs/runs/list",
            params={"job_id": job_id, "limit": limit},
            headers=self._headers(),
        )
        resp.raise_for_status()
        return resp.json().get("runs", [])

    async def get_run_output(self, run_id: int) -> dict:
        """Retorna output/logs de uma run."""
        await self._ensure_credentials()
        resp = await self._client().get(
            f"{self._host}/api/2.1/jobs/runs/get-output",
            params={"run_id": run_id},
            headers=self._headers(),
        )
        resp.raise_for_status()
        return resp.json()

    async def _resolve_warehouse_id(self) -> str:
        """Resolve um warehouse_id valido (e RUNNING) via SQL Warehouses API.

        Databricks SQL Statement API NAO aceita "auto" como warehouse_id
        — exige UUID de um warehouse existente. Caso o warehouse esteja
        STOPPED, dispara start + poll ate RUNNING (max 60s, suficiente
        pro cold-start de Serverless Starter Warehouse).
        """
        if self._warehouse_id:
            # Reconferir state — warehouse pode ter parado por idle timeout.
            try:
                state = await self._get_warehouse_state(self._warehouse_id)
                if "RUNNING" in state or "STARTING" in state:
                    return self._warehouse_id
            except httpx.HTTPError:
                self._warehouse_id = None  # cache invalido, re-resolve

        list_resp = await self._client().get(
            f"{self._host}/api/2.0/sql/warehouses",
            headers=self._headers(),
            timeout=10,
        )
        list_resp.raise_for_status()
        warehouses = list_resp.json().get("warehouses", [])
        if not warehouses:
            raise RuntimeError(
                "Nenhum SQL Warehouse no workspace — criar via Databricks UI"
            )

        # Preferir RUNNING; fallback pro primeiro
        running = next(
            (wh for wh in warehouses if "RUNNING" in str(wh.get("state", ""))),
            None,
        )
        chosen = running or warehouses[0]
        wh_id = chosen["id"]
        state = str(chosen.get("state", ""))

        if "RUNNING" not in state:
            logger.info(
                "Starting SQL warehouse", warehouse_id=wh_id, state=state,
            )
            start_resp = await self._client().post(
                f"{self._host}/api/2.0/sql/warehouses/{wh_id}/start",
                headers=self._headers(),
                timeout=10,
            )
            start_resp.raise_for_status()
            # Poll ate RUNNING (max 60s — Serverless Starter cold-start ~5s).
            for _ in range(12):
                await asyncio.sleep(5)
                current = await self._get_warehouse_state(wh_id)
                if "RUNNING" in current:
                    break
            else:
                raise RuntimeError(
                    f"Warehouse {wh_id} nao subiu em 60s"
                )

        self._warehouse_id = wh_id
        return wh_id

    async def _get_warehouse_state(self, warehouse_id: str) -> str:
        resp = await self._client().get(
            f"{self._host}/api/2.0/sql/warehouses/{warehouse_id}",
            headers=self._headers(),
            timeout=10,
        )
        resp.raise_for_status()
        return str(resp.json().get("state", ""))

    async def query_table(self, sql: str, max_rows: int = 100) -> dict:
        """Executa query SQL via Databricks SQL Statement API.

        Resolve warehouse_id em runtime — antes mandava `"auto"` que a API
        rejeitava com 400 Bad Request. Cacheia o ID e auto-starta o
        warehouse se necessario.
        """
        await self._ensure_credentials()
        warehouse_id = await self._resolve_warehouse_id()
        resp = await self._client().post(
            f"{self._host}/api/2.0/sql/statements",
            json={
                "statement": sql,
                "warehouse_id": warehouse_id,
                "wait_timeout": "30s",
                "row_limit": max_rows,
            },
            headers=self._headers(),
            timeout=60,
        )
        resp.raise_for_status()
        return resp.json()

    async def trigger_run(self, job_id: int) -> dict:
        """Dispara execucao manual do job."""
        await self._ensure_credentials()
        resp = await self._client().post(
            f"{self._host}/api/2.1/jobs/run-now",
            json={"job_id": job_id},
            headers=self._headers(),
        )
        resp.raise_for_status()
        return resp.json()

    async def get_table_schemas(self, catalog: str = "medallion") -> list[dict]:
        """Lista schemas das tabelas via Unity Catalog.

        T7 Phase 4: as 3 chamadas (bronze/silver/gold) agora rodam em
        paralelo via asyncio.gather — antes eram sequenciais.
        """
        await self._ensure_credentials()
        schema_names = ["bronze", "silver", "gold"]
        results = await asyncio.gather(
            *(self._fetch_schema(catalog, name) for name in schema_names),
            return_exceptions=True,
        )
        schemas: list[dict] = []
        for name, result in zip(schema_names, results, strict=True):
            if isinstance(result, Exception):
                logger.warning(
                    "Erro ao listar schemas", schema=name, error=str(result)
                )
                continue
            schemas.extend(result)
        return schemas

    async def _fetch_schema(self, catalog: str, schema_name: str) -> list[dict]:
        """Busca tabelas de um único schema. Usado por `get_table_schemas`."""
        resp = await self._client().get(
            f"{self._host}/api/2.1/unity-catalog/tables",
            params={"catalog_name": catalog, "schema_name": schema_name},
            headers=self._headers(),
        )
        if resp.status_code != 200:
            return []
        return [
            {
                "catalog": catalog,
                "schema": schema_name,
                "table": table["name"],
                "columns": [
                    {"name": c["name"], "type": c["type_name"]}
                    for c in table.get("columns", [])
                ],
            }
            for table in resp.json().get("tables", [])
        ]

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

    async def get_table_history(self, table: str, limit: int = 10) -> list[dict]:
        """Retorna historico de versoes Delta via DESCRIBE HISTORY."""
        await self._ensure_credentials()
        sql = build_describe_history_sql(table, limit)
        result = await self.query_table(sql, max_rows=limit)
        return _parse_history_result(result)

    async def restore_table(
        self,
        table: str,
        *,
        version: int | None = None,
        timestamp: str | None = None,
    ) -> dict:
        """Executa RESTORE TABLE ... TO VERSION/TIMESTAMP AS OF via SQL."""
        await self._ensure_credentials()
        sql = build_restore_table_sql(table, version=version, timestamp=timestamp)
        return await self.query_table(sql)


# ---------------------------------------------------------------------------
# Helpers de SQL Delta (funções puras — fáceis de testar sem I/O)
# ---------------------------------------------------------------------------


def _quote_delta_table(table: str) -> str:
    """Quote cada segmento de catalog.schema.table para SQL Delta."""
    parts = table.strip().split(".")
    return ".".join(f"`{p}`" for p in parts)


def build_describe_history_sql(table: str, limit: int = 10) -> str:
    """Gera SQL DESCRIBE HISTORY para buscar historico de versoes Delta."""
    return f"DESCRIBE HISTORY {_quote_delta_table(table)} LIMIT {limit}"


def build_restore_table_sql(
    table: str,
    *,
    version: int | None = None,
    timestamp: str | None = None,
) -> str:
    """Gera SQL RESTORE TABLE ... TO VERSION AS OF <v> ou TIMESTAMP AS OF '<ts>'."""
    quoted = _quote_delta_table(table)
    if version is not None:
        return f"RESTORE TABLE {quoted} TO VERSION AS OF {version}"
    if timestamp is not None:
        return f"RESTORE TABLE {quoted} TO TIMESTAMP AS OF '{timestamp}'"
    raise ValueError("version ou timestamp obrigatorio para RESTORE TABLE")


def _parse_history_result(result: dict) -> list[dict]:
    """Converte resposta da Statement API em lista de versoes."""
    state = result.get("status", {}).get("state", "")
    if state != "SUCCEEDED":
        return []
    columns = [
        c["name"]
        for c in result.get("manifest", {}).get("schema", {}).get("columns", [])
    ]
    rows = result.get("result", {}).get("data_array", [])
    return [dict(zip(columns, row, strict=False)) for row in rows]


def _ms_to_iso(ms: int | None) -> str | None:
    """Converte timestamp Databricks (milissegundos Unix) pra ISO string SP."""
    if not ms:
        return None
    from datetime import datetime, timedelta, timezone

    dt = datetime.fromtimestamp(ms / 1000, tz=timezone(timedelta(hours=-3)))
    return dt.strftime("%Y-%m-%d %H:%M:%S (horario de Brasilia)")
