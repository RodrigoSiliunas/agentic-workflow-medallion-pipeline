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
# UC credential/location names: letters, digits, `_`, `-` (max 256 chars)
_UC_NAME_RE = re.compile(r"^[a-zA-Z0-9_-]{1,200}$")


def _resolve_project(ctx: StepContext) -> str:
    project = ctx.env_vars().get("project_name", "medallion-pipeline")
    if not _UC_NAME_RE.match(project):
        raise ValueError(
            f"project_name invalido: '{project}'. "
            "Use letras, digitos, underscores, hifens (max 200)."
        )
    return project


@register_saga_step("catalog")
class CatalogStep:
    step_id = "catalog"

    async def compensate(self, ctx: StepContext) -> None:
        """Rollback: drop catalog + storage credential + external location SE criados.

        DROP CATALOG cascateia schemas — saga falha rollback acontece antes de
        qualquer write de dados, entao seguro. Skip se catalog ja existia.
        """
        if not ctx.shared.databricks_catalog_created:
            await ctx.info("compensate(catalog): catalog nao foi criado — skip")
            return
        catalog_name = ctx.shared.catalog
        if not catalog_name:
            return
        w = workspace_client(ctx.credentials)
        try:
            def _drop() -> None:
                w.catalogs.delete(name=catalog_name, force=True)
                cred = ctx.shared.databricks_storage_credential
                loc = ctx.shared.databricks_external_location
                if loc:
                    w.external_locations.delete(name=loc, force=True)
                if cred:
                    w.storage_credentials.delete(name=cred, force=True)

            await asyncio.to_thread(_drop)
            await ctx.info(
                f"compensate(catalog): catalog {catalog_name} + UC objects removidos"
            )
        except Exception as exc:  # noqa: BLE001
            await ctx.warn(f"compensate(catalog) falhou: {exc}")

    async def execute(self, ctx: StepContext) -> None:
        catalog = ctx.env_vars().get("catalog", "medallion")
        if not _IDENTIFIER_RE.match(catalog):
            raise ValueError(
                f"Nome do catalog invalido: '{catalog}'. "
                "Use apenas letras minusculas, numeros e underscores (max 64 chars)."
            )
        w = workspace_client(ctx.credentials)

        # Storage Credential + External Location — necessario pro metastore
        # acessar o S3 bucket. Precedencia do bucket: shared (setado pelo
        # S3Step) > env var (user input). Se nem role nem bucket disponivel,
        # pula criacao — catalog usara managed storage do metastore.
        s3_bucket = ctx.shared.s3_bucket or ctx.env_vars().get("s3_bucket", "")
        role_arn = ctx.shared.databricks_role_arn
        project = _resolve_project(ctx)

        managed_location: str | None = None
        if s3_bucket and role_arn:
            # Suffix por company — metastore pode ser compartilhado entre
            # workspaces/accounts. Nomes globais precisam ser unicos por tenant.
            company_suffix = str(ctx.company_id).split("-")[0]
            cred_name = f"{project}-{company_suffix}-s3-credential"
            loc_name = f"{project}-{company_suffix}-datalake"
            # Databricks gera external_id ao criar Storage Credential.
            # Retornado aqui pra atualizar trust policy da role.
            external_id = await self._ensure_storage_credential(
                ctx, w, cred_name, role_arn
            )
            if external_id:
                # Atualiza trust policy com Condition sts:ExternalId
                # (hardening confused-deputy). Import tardio pra evitar ciclo.
                from app.services.real_saga.steps.iam import (
                    update_trust_policy_with_external_id,
                )

                await update_trust_policy_with_external_id(
                    ctx, role_arn, external_id
                )
                ctx.shared.databricks_external_id = external_id

            # Prefix por company — multi-tenant sharing do mesmo bucket.
            # Evita overlap com external locations de outros tenants.
            bucket_prefix = f"{company_suffix}"
            await self._ensure_external_location(
                ctx, w, loc_name, cred_name, s3_bucket, bucket_prefix
            )
            ctx.shared.databricks_storage_credential = cred_name
            ctx.shared.databricks_external_location = loc_name
            # Catalog usa external_location como managed storage
            managed_location = f"s3://{s3_bucket}/{bucket_prefix}/catalog"

        # Catalog via SDK API (idempotente — pula se ja existe)
        await self._ensure_catalog(ctx, w, catalog, managed_location)
        await ctx.info(f"Catalog '{catalog}' ok")

        # Schemas via SDK API (idempotente e nao depende de SQL warehouse storage)
        for schema in _SCHEMAS:
            await self._ensure_schema(ctx, w, catalog, schema)
        await ctx.info(f"Schemas: {', '.join(f'{catalog}.{s}' for s in _SCHEMAS)}")

        # Transfere ownership + grant ALL_PRIVILEGES pro admin user — saga
        # roda com service principal, mas cluster jobs rodam como admin.
        # Sem isso, bronze.saveAsTable da PERMISSION_DENIED BROWSE.
        admin_email = ctx.env_vars().get("admin_email", "administrator@idlehub.com.br")
        await self._grant_admin_access(ctx, w, catalog, admin_email)

        await ctx.success(f"Unity Catalog pronto: {catalog}.{{{','.join(_SCHEMAS)}}}")
        ctx.shared.catalog = catalog

    @staticmethod
    async def _grant_admin_access(
        ctx: StepContext, w: WorkspaceClient, catalog: str, admin_email: str
    ) -> None:
        """Transfere ownership do catalog/schemas/EL/SC + grants ALL_PRIVILEGES
        pro admin user. Cluster jobs rodam como admin, precisam acessar."""

        def _do() -> None:
            # Catalog ownership + ALL_PRIVILEGES
            w.api_client.do(
                "PATCH",
                f"/api/2.1/unity-catalog/catalogs/{catalog}",
                body={"owner": admin_email},
            )
            w.api_client.do(
                "PATCH",
                f"/api/2.1/unity-catalog/permissions/catalog/{catalog}",
                body={
                    "changes": [
                        {"principal": admin_email, "add": ["ALL_PRIVILEGES"]},
                    ]
                },
            )
            # Schemas
            for schema in _SCHEMAS:
                w.api_client.do(
                    "PATCH",
                    f"/api/2.1/unity-catalog/permissions/schema/{catalog}.{schema}",
                    body={
                        "changes": [
                            {"principal": admin_email, "add": ["ALL_PRIVILEGES"]},
                        ]
                    },
                )
            # External Location + Storage Credential
            cred_name = ctx.shared.databricks_storage_credential
            loc_name = ctx.shared.databricks_external_location
            if cred_name:
                w.api_client.do(
                    "PATCH",
                    f"/api/2.1/unity-catalog/permissions/storage_credential/{cred_name}",
                    body={"changes": [{"principal": admin_email, "add": ["ALL_PRIVILEGES"]}]},
                )
            if loc_name:
                w.api_client.do(
                    "PATCH",
                    f"/api/2.1/unity-catalog/permissions/external_location/{loc_name}",
                    body={"changes": [{"principal": admin_email, "add": ["ALL_PRIVILEGES"]}]},
                )

        await asyncio.to_thread(_do)
        await ctx.info(f"Grant ALL_PRIVILEGES em UC objects -> {admin_email}")

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
        ctx: StepContext,
        w: WorkspaceClient,
        catalog: str,
        managed_location: str | None = None,
    ) -> None:
        def _ensure() -> bool:
            existing = [c for c in w.catalogs.list() if c.name == catalog]
            if existing:
                return False
            kwargs: dict = {
                "name": catalog,
                "comment": "Flowertex platform — medallion pipeline",
            }
            if managed_location:
                kwargs["storage_root"] = managed_location
            w.catalogs.create(**kwargs)
            return True

        was_created = await asyncio.to_thread(_ensure)
        if was_created:
            ctx.shared.databricks_catalog_created = True

    @staticmethod
    async def _ensure_storage_credential(
        ctx: StepContext,
        w: WorkspaceClient,
        cred_name: str,
        role_arn: str,
    ) -> str | None:
        """Cria ou recupera Storage Credential. Retorna external_id gerado
        pelo Databricks — necessario pra atualizar trust policy da role."""

        def _ensure() -> tuple[str, str | None]:
            for cred in w.storage_credentials.list():
                if cred.name == cred_name:
                    ext_id = (
                        cred.aws_iam_role.external_id if cred.aws_iam_role else None
                    )
                    return "exists", ext_id
            # skip_validation=True: Databricks nao tenta assumir role no create.
            # Chicken-and-egg: self-assuming trust exige role ARN, role ARN
            # exige SC criada pra ter external_id. Skip + update trust depois.
            created = w.storage_credentials.create(
                name=cred_name,
                aws_iam_role=AwsIamRoleRequest(role_arn=role_arn),
                comment="Cross-account S3 access for medallion pipeline",
                skip_validation=True,
            )
            ext_id = (
                created.aws_iam_role.external_id if created.aws_iam_role else None
            )
            return "created", ext_id

        status, external_id = await asyncio.to_thread(_ensure)
        ext_note = (
            f"external_id={external_id[:8]}..." if external_id else "no external_id"
        )
        await ctx.info(f"Storage credential '{cred_name}' ({ext_note}): {status}")

        # Grant self CREATE_EXTERNAL_LOCATION — owner nao tem implicitamente
        # esse privilegio em UC, precisa ser explicito. Roda sempre (idempotente).
        def _grant() -> str:
            me = w.current_user.me()
            principal = me.user_name or ""
            if not principal:
                raise RuntimeError("Falha ao obter user_name do current_user")
            # SDK enum SecurableType.STORAGE_CREDENTIAL serializa como
            # "SECURABLETYPE.STORAGE_CREDENTIAL" (invalido). API aceita
            # string lowercase "storage_credential" via permissions endpoint.
            w.api_client.do(
                "PATCH",
                f"/api/2.1/unity-catalog/permissions/storage_credential/{cred_name}",
                body={
                    "changes": [
                        {
                            "principal": principal,
                            "add": ["CREATE_EXTERNAL_LOCATION"],
                        }
                    ]
                },
            )
            return principal

        principal = await asyncio.to_thread(_grant)
        await ctx.info(
            f"Grant CREATE_EXTERNAL_LOCATION em '{cred_name}' -> {principal}"
        )

        return external_id

    @staticmethod
    async def _ensure_external_location(
        ctx: StepContext,
        w: WorkspaceClient,
        loc_name: str,
        cred_name: str,
        bucket: str,
        prefix: str = "",
    ) -> None:
        url = f"s3://{bucket}/{prefix}" if prefix else f"s3://{bucket}"

        def _list_existing() -> str | None:
            for loc in w.external_locations.list():
                if loc.name == loc_name:
                    return "exists"
            return None

        existing = await asyncio.to_thread(_list_existing)
        if existing:
            await ctx.info(f"External location '{loc_name}' -> {url}: exists")
            return

        # skip_validation=True: Databricks nao testa READ S3 no create.
        # Necessario para deploy one-click — sem skip, chicken-and-egg
        # entre IAM propagation, trust policy update, e S3 access.
        # Real S3 access sera testado quando primeira query UC rodar.
        def _create() -> None:
            w.external_locations.create(
                name=loc_name,
                url=url,
                credential_name=cred_name,
                comment="S3 datalake for medallion pipeline",
                skip_validation=True,
            )

        await asyncio.to_thread(_create)
        await ctx.info(
            f"External location '{loc_name}' -> {url}: created (skip_validation)"
        )

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
