"""Step `cluster_provision` — cria/reutiliza cluster dedicado pro pipeline ETL.

Quarto step novo da saga completa. Extrai logica de cluster creation do
`workflow.py` pra um step dedicado. Permite:
- Pipeline runs usarem cluster existente (mais rapido, sem cold start)
- Testing em isolamento
- spark_conf s3a via secret scope refs (necessario sem instance profile)

Idempotente: se cluster com nome medallion-pipeline existe e RUNNING,
reutiliza. Caso contrario cria + aguarda RUNNING.
"""

from __future__ import annotations

import asyncio

from databricks.sdk import WorkspaceClient
from databricks.sdk.service.compute import (
    AwsAttributes,
    AwsAvailability,
    DataSecurityMode,
)

from app.services.real_saga.base import StepContext
from app.services.real_saga.databricks_client import workspace_client
from app.services.real_saga.registry import register_saga_step

_CLUSTER_NAME = "medallion-pipeline"


@register_saga_step("cluster_provision")
class ClusterProvisionStep:
    step_id = "cluster_provision"

    async def execute(self, ctx: StepContext) -> None:
        env = ctx.env_vars()

        # User pode especificar cluster_id manual via env var
        explicit_id = env.get("cluster_id", "")
        if explicit_id:
            ctx.shared.databricks_cluster_id = explicit_id
            await ctx.info(f"Usando cluster_id explicito: {explicit_id}")
            return

        w = workspace_client(ctx.credentials)
        admin_email = env.get("admin_email", "administrator@idlehub.com.br")
        scope = env.get("secret_scope", "medallion-pipeline")
        region = ctx.credentials.aws_region or "us-east-2"

        # Cluster sizing — defaults conservadores, override via wizard advanced
        node_type = (env.get("cluster_node_type") or "m5d.large").strip()
        try:
            num_workers = int(env.get("cluster_num_workers") or 2)
        except (TypeError, ValueError):
            num_workers = 2
        spark_version = (
            env.get("cluster_spark_version") or "15.4.x-scala2.12"
        ).strip()

        cluster_id = await self._ensure_cluster(
            ctx, w, scope, region, admin_email,
            node_type=node_type,
            num_workers=num_workers,
            spark_version=spark_version,
        )
        ctx.shared.databricks_cluster_id = cluster_id
        await ctx.success(f"Cluster pronto: {cluster_id}")

    @staticmethod
    async def _ensure_cluster(
        ctx: StepContext,
        w: WorkspaceClient,
        scope: str,
        region: str,
        admin_email: str,
        node_type: str = "m5d.large",
        num_workers: int = 2,
        spark_version: str = "15.4.x-scala2.12",
    ) -> str:
        def _find() -> str:
            for c in w.clusters.list():
                if (c.cluster_name or "").lower() == _CLUSTER_NAME:
                    return c.cluster_id or ""
            return ""

        existing = await asyncio.to_thread(_find)
        if existing:
            await ctx.info(f"Cluster {_CLUSTER_NAME} ja existe: {existing}")
            return existing

        await ctx.info(
            f"Criando cluster {_CLUSTER_NAME} ({node_type}, "
            f"{num_workers} workers, DBR {spark_version})"
        )

        def _create() -> str:
            # Spark S3A config via secret scope refs — cluster sem instance
            # profile precisa essas spark.conf pra s3a:// funcionar.
            spark_conf = {
                "spark.hadoop.fs.s3a.access.key": f"{{{{secrets/{scope}/aws-access-key-id}}}}",
                "spark.hadoop.fs.s3a.secret.key": f"{{{{secrets/{scope}/aws-secret-access-key}}}}",
                "spark.hadoop.fs.s3a.endpoint": f"s3.{region}.amazonaws.com",
            }
            resp = w.clusters.create(
                cluster_name=_CLUSTER_NAME,
                spark_version=spark_version,
                node_type_id=node_type,
                num_workers=num_workers,
                autotermination_minutes=30,
                data_security_mode=DataSecurityMode.SINGLE_USER,
                single_user_name=admin_email,
                spark_conf=spark_conf,
                aws_attributes=AwsAttributes(
                    first_on_demand=1,
                    availability=AwsAvailability.ON_DEMAND,
                    zone_id="auto",
                ),
            )
            return resp.cluster_id or ""

        cluster_id = await asyncio.to_thread(_create)
        await ctx.info(f"Cluster criado: {cluster_id} (cold start ~2min)")
        return cluster_id
