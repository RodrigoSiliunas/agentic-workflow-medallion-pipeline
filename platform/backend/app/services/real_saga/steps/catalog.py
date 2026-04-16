"""Step `catalog` — cria Unity Catalog + schemas idempotentemente.

Executa SQL via SQL Warehouse do Databricks. Se nenhum warehouse esta
rodando, inicia o primeiro disponivel automaticamente (respeitando o
wait_timeout=50s limite do statement execution API).

Schemas criados:
- bronze, silver, gold (obrigatorios para o pipeline)
- pipeline (tabelas de metadata + volume tmp)
- observer (tabela `diagnostics` do Observer Agent)
"""

from __future__ import annotations

import asyncio
import re
import time

from databricks.sdk import WorkspaceClient
from databricks.sdk.service.catalog import AwsIamRoleRequest
from databricks.sdk.service.sql import StatementState

from app.services.real_saga.base import StepContext
from app.services.real_saga.databricks_client import workspace_client
from app.services.real_saga.registry import register_saga_step

_SCHEMAS = ["bronze", "silver", "gold", "pipeline", "observer"]
_IDENTIFIER_RE = re.compile(r"^[a-z][a-z0-9_]{0,63}$")


@register_saga_step("catalog")
class CatalogStep:
    step_id = "catalog"

    async def execute(self, ctx: StepContext) -> None:
        catalog = ctx.env_vars().get("catalog", "medallion")
        if not _IDENTIFIER_RE.match(catalog):
            raise ValueError(
                f"Nome do catalog invalido: '{catalog}'. "
                "Use apenas letras minusculas, numeros e underscores (max 64 chars)."
            )
        w = workspace_client(ctx.credentials)

        # Storage Credential + External Location — necessario pro metastore
        # acessar o S3 bucket (nao obrigatorio se o catalog ja existe).
        s3_bucket = ctx.env_vars().get("s3_bucket", "")
        role_arn = ctx.shared.databricks_role_arn
        if s3_bucket and role_arn:
            await self._ensure_storage_credential(ctx, w, role_arn)
            await self._ensure_external_location(ctx, w, s3_bucket)

        # Catalog via SDK API (idempotente — pula se ja existe)
        await self._ensure_catalog(ctx, w, catalog)
        await ctx.info(f"Catalog '{catalog}' ok")

        # Schemas via SDK API (idempotente e nao depende de SQL warehouse storage)
        for schema in _SCHEMAS:
            await self._ensure_schema(ctx, w, catalog, schema)
        await ctx.info(f"Schemas: {', '.join(f'{catalog}.{s}' for s in _SCHEMAS)}")

        await ctx.success(f"Unity Catalog pronto: {catalog}.{{{','.join(_SCHEMAS)}}}")
        ctx.shared.catalog = catalog

    @staticmethod
    async def _ensure_schema(
        ctx: StepContext, w: WorkspaceClient, catalog: str, schema: str
    ) -> None:
        def _ensure() -> None:
            existing = [s for s in w.schemas.list(catalog_name=catalog) if s.name == schema]
            if existing:
                return
            w.schemas.create(name=schema, catalog_name=catalog, comment=f"Camada {schema}")

        await asyncio.to_thread(_ensure)

    @staticmethod
    async def _ensure_catalog(
        ctx: StepContext, w: WorkspaceClient, catalog: str
    ) -> None:
        def _ensure() -> None:
            existing = [c for c in w.catalogs.list() if c.name == catalog]
            if existing:
                return
            w.catalogs.create(name=catalog, comment="Safatechx platform — medallion pipeline")

        await asyncio.to_thread(_ensure)

    @staticmethod
    async def _ensure_storage_credential(
        ctx: StepContext, w: WorkspaceClient, role_arn: str
    ) -> None:
        cred_name = "medallion-s3-credential"

        def _ensure() -> str:
            for cred in w.storage_credentials.list():
                if cred.name == cred_name:
                    return "exists"
            w.storage_credentials.create(
                name=cred_name,
                aws_iam_role=AwsIamRoleRequest(role_arn=role_arn),
                comment="Cross-account S3 access for medallion pipeline",
            )
            return "created"

        result = await asyncio.to_thread(_ensure)
        await ctx.info(f"Storage credential '{cred_name}': {result}")

    @staticmethod
    async def _ensure_external_location(
        ctx: StepContext, w: WorkspaceClient, bucket: str
    ) -> None:
        loc_name = "medallion-datalake"
        url = f"s3://{bucket}"

        def _ensure() -> str:
            for loc in w.external_locations.list():
                if loc.name == loc_name:
                    return "exists"
            w.external_locations.create(
                name=loc_name,
                url=url,
                credential_name="medallion-s3-credential",
                comment="S3 datalake for medallion pipeline",
            )
            return "created"

        result = await asyncio.to_thread(_ensure)
        await ctx.info(f"External location '{loc_name}': {result}")

    @staticmethod
    async def _ensure_warehouse(ctx: StepContext, w: WorkspaceClient) -> str:
        def _find() -> tuple[str | None, str | None]:
            warehouses = list(w.warehouses.list())
            if not warehouses:
                return (None, None)
            # Prefere um que ja esta running
            running = next(
                (wh for wh in warehouses if str(wh.state) == "State.RUNNING"), None
            )
            chosen = running or warehouses[0]
            return (chosen.id, str(chosen.state))

        wh_id, state = await asyncio.to_thread(_find)
        if wh_id is None:
            raise RuntimeError(
                "Nenhum SQL Warehouse encontrado no workspace — crie um no Databricks UI "
                "(Settings -> SQL Warehouses) ou rode o pipeline num workspace que tenha."
            )

        if state != "State.RUNNING":
            await ctx.info(f"Warehouse {wh_id} esta em {state} — iniciando")
            await asyncio.to_thread(lambda: w.warehouses.start(wh_id))
            # Polling ate RUNNING (max 5min — serverless warehouses no trial
            # podem levar ate 4min no cold start)
            deadline = time.monotonic() + 300
            while time.monotonic() < deadline:
                await asyncio.sleep(5)

                def _state() -> str:
                    return str(w.warehouses.get(wh_id).state)

                current = await asyncio.to_thread(_state)
                if current == "State.RUNNING":
                    break
                await ctx.info(f"  warehouse ainda {current}")
            else:
                raise TimeoutError(
                    f"SQL Warehouse {wh_id} nao entrou em RUNNING em 3min"
                )
        return wh_id

    @staticmethod
    async def _exec_sql(
        ctx: StepContext,
        w: WorkspaceClient,
        warehouse_id: str,
        statement: str,
    ) -> None:
        def _run() -> None:
            # wait_timeout maximo e 50s (limite do statement execution API)
            result = w.statement_execution.execute_statement(
                warehouse_id=warehouse_id,
                statement=statement,
                wait_timeout="30s",
            )
            state = result.status.state if result.status else None
            if state == StatementState.FAILED:
                msg = result.status.error.message if result.status and result.status.error else "?"
                raise RuntimeError(f"SQL falhou: {msg}")

        await asyncio.to_thread(_run)
