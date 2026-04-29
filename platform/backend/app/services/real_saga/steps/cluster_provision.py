"""Step `cluster_provision` — cria/reutiliza cluster dedicado pro pipeline ETL.

Suporta:
- Custom cluster name (default: medallion-pipeline)
- Driver e worker node types separados
- Sizing fixo OU autoscale (min/max workers)
- Cluster policy enforcement (allowlist + max workers)
- Custom tags pra billing tracking

Idempotente: cluster reusado se config bate; reconfigurado via edit se muda.
"""

from __future__ import annotations

import asyncio
import json

from databricks.sdk import WorkspaceClient
from databricks.sdk.service.compute import (
    AutoScale,
    AwsAttributes,
    AwsAvailability,
    DataSecurityMode,
)

from app.services.real_saga.base import StepContext
from app.services.real_saga.databricks_client import workspace_client
from app.services.real_saga.registry import register_saga_step

_DEFAULT_CLUSTER_NAME = "medallion-pipeline"


@register_saga_step("cluster_provision")
class ClusterProvisionStep:
    step_id = "cluster_provision"

    async def compensate(self, ctx: StepContext) -> None:
        """Rollback: termina cluster + deleta policy custom se criados nesta saga.

        - cluster: permanent delete via SDK (vs terminate, que mantem cluster_id).
          Pra rollback atomico precisa REMOVER (cluster_provision idempotency
          preserva nome — proximo retry recria limpo).
        - policy: deleta SE foi custom criada pela saga.
        - Skip se cluster_id_explicit (user reusou ID — nao mexer).
        """
        w = workspace_client(ctx.credentials)

        if ctx.shared.databricks_cluster_created and ctx.shared.databricks_cluster_id:
            cluster_id = ctx.shared.databricks_cluster_id
            try:
                await asyncio.to_thread(lambda: w.clusters.permanent_delete(cluster_id=cluster_id))
                await ctx.info(f"compensate(cluster): cluster {cluster_id} removido")
            except Exception as exc:  # noqa: BLE001
                await ctx.warn(f"compensate(cluster) falhou: {exc}")
        else:
            await ctx.info("compensate(cluster): cluster nao foi criado — skip")

        if ctx.shared.databricks_cluster_policy_created and ctx.shared.databricks_cluster_policy_id:
            pid = ctx.shared.databricks_cluster_policy_id
            try:
                await asyncio.to_thread(lambda: w.cluster_policies.delete(policy_id=pid))
                await ctx.info(f"compensate(cluster): policy {pid} removida")
            except Exception as exc:  # noqa: BLE001
                await ctx.warn(f"compensate(cluster policy) falhou: {exc}")

    @staticmethod
    async def _upsert_custom_policy(
        ctx: StepContext, w: WorkspaceClient, cluster_name: str, policy_json: str,
    ) -> str:
        """Cria/atualiza cluster policy custom no workspace, retorna policy_id.

        Idempotente: usa nome derivado do cluster (`{cluster_name}-policy`).
        Se ja existe, edit. Senao create.
        """
        try:
            json.loads(policy_json)  # valida sintaxe antes de chamar API
        except json.JSONDecodeError as exc:
            raise RuntimeError(f"cluster_policy_definition JSON invalido: {exc}") from exc

        policy_name = f"{cluster_name}-policy"

        def _do() -> str:
            for p in w.cluster_policies.list():
                if (p.name or "").lower() == policy_name.lower():
                    w.cluster_policies.edit(
                        policy_id=p.policy_id or "",
                        name=policy_name,
                        definition=policy_json,
                    )
                    return p.policy_id or ""
            created = w.cluster_policies.create(
                name=policy_name,
                definition=policy_json,
            )
            return created.policy_id or ""

        policy_id = await asyncio.to_thread(_do)
        await ctx.info(f"Policy custom registrada: {policy_name} (id={policy_id})")
        return policy_id

    async def execute(self, ctx: StepContext) -> None:
        env = ctx.env_vars()

        explicit_id = env.get("cluster_id", "")
        if explicit_id:
            ctx.shared.databricks_cluster_id = explicit_id
            await ctx.info(f"Usando cluster_id explicito: {explicit_id}")
            return

        w = workspace_client(ctx.credentials)
        admin_email = env.get("admin_email", "administrator@idlehub.com.br")
        scope = env.get("secret_scope", "medallion-pipeline")
        region = ctx.credentials.aws_region or "us-east-2"

        cluster_name = (env.get("cluster_name") or _DEFAULT_CLUSTER_NAME).strip()

        # Sizing: node_type aplica a worker; driver_node_type opcional (default = igual)
        node_type = (env.get("cluster_node_type") or "m5d.large").strip()
        driver_node_type = (env.get("cluster_driver_node_type") or node_type).strip()
        spark_version = (
            env.get("cluster_spark_version") or "15.4.x-scala2.12"
        ).strip()

        try:
            autotermination_min = int(env.get("cluster_autotermination_min") or 30)
        except (TypeError, ValueError):
            autotermination_min = 30

        # Autoscale tem precedencia sobre num_workers fixo
        autoscale_min_raw = env.get("cluster_autoscale_min")
        autoscale_max_raw = env.get("cluster_autoscale_max")
        autoscale = None
        num_workers: int | None = None
        if autoscale_min_raw and autoscale_max_raw:
            try:
                autoscale = (int(autoscale_min_raw), int(autoscale_max_raw))
            except (TypeError, ValueError):
                autoscale = None
        if autoscale is None:
            try:
                num_workers = int(env.get("cluster_num_workers") or 2)
            except (TypeError, ValueError):
                num_workers = 2

        # Policy: custom JSON tem precedencia (registra no workspace + reusa
        # cluster_policy_id). Senao, usa policy_id ja existente.
        policy_id = env.get("cluster_policy_id") or None
        policy_definition = env.get("cluster_policy_definition")
        if policy_definition:
            policy_id = await self._upsert_custom_policy(
                ctx, w, env.get("cluster_name") or _DEFAULT_CLUSTER_NAME,
                policy_definition,
            )

        custom_tags: dict[str, str] = {}
        tags_raw = env.get("cluster_tags")
        if tags_raw:
            try:
                parsed = json.loads(tags_raw)
                if isinstance(parsed, dict):
                    custom_tags = {str(k): str(v) for k, v in parsed.items()}
            except (TypeError, ValueError, json.JSONDecodeError):
                await ctx.warn(f"cluster_tags invalido (esperado JSON dict): {tags_raw}")

        cluster_id, was_created = await self._ensure_cluster(
            ctx, w, scope, region, admin_email,
            cluster_name=cluster_name,
            node_type=node_type,
            driver_node_type=driver_node_type,
            num_workers=num_workers,
            autoscale=autoscale,
            spark_version=spark_version,
            autotermination_min=autotermination_min,
            policy_id=policy_id,
            custom_tags=custom_tags,
        )
        ctx.shared.databricks_cluster_id = cluster_id
        ctx.shared.databricks_cluster_created = was_created
        ctx.shared.databricks_cluster_policy_id = policy_id
        if env.get("cluster_policy_definition"):
            ctx.shared.databricks_cluster_policy_created = True
        await ctx.success(f"Cluster pronto: {cluster_id}")

    @staticmethod
    async def _ensure_cluster(
        ctx: StepContext,
        w: WorkspaceClient,
        scope: str,
        region: str,
        admin_email: str,
        *,
        cluster_name: str,
        node_type: str,
        driver_node_type: str,
        num_workers: int | None,
        autoscale: tuple[int, int] | None,
        spark_version: str,
        autotermination_min: int,
        policy_id: str | None,
        custom_tags: dict[str, str],
    ) -> tuple[str, bool]:
        def _spark_conf() -> dict[str, str]:
            return {
                "spark.hadoop.fs.s3a.access.key": f"{{{{secrets/{scope}/aws-access-key-id}}}}",
                "spark.hadoop.fs.s3a.secret.key": f"{{{{secrets/{scope}/aws-secret-access-key}}}}",
                "spark.hadoop.fs.s3a.endpoint": f"s3.{region}.amazonaws.com",
            }

        def _build_kwargs() -> dict:
            """Kwargs comum pra create + edit. Inclui sizing strategy."""
            kwargs: dict = {
                "cluster_name": cluster_name,
                "spark_version": spark_version,
                "node_type_id": node_type,
                "driver_node_type_id": driver_node_type,
                "autotermination_minutes": autotermination_min,
                "data_security_mode": DataSecurityMode.SINGLE_USER,
                "single_user_name": admin_email,
                "spark_conf": _spark_conf(),
                "aws_attributes": AwsAttributes(
                    first_on_demand=1,
                    availability=AwsAvailability.ON_DEMAND,
                    zone_id="auto",
                ),
            }
            if autoscale is not None:
                kwargs["autoscale"] = AutoScale(min_workers=autoscale[0], max_workers=autoscale[1])
            else:
                kwargs["num_workers"] = num_workers or 2
            if policy_id:
                kwargs["policy_id"] = policy_id
            if custom_tags:
                kwargs["custom_tags"] = custom_tags
            return kwargs

        def _find_existing() -> tuple[
            str, str | None, str | None, int | None, str | None,
            int | None, int | None, dict[str, str] | None,
        ]:
            """Retorna (id, node, driver_node, workers, spark, autoscale_min/max, tags)."""
            for c in w.clusters.list():
                if (c.cluster_name or "").lower() == cluster_name.lower():
                    autosc = c.autoscale
                    return (
                        c.cluster_id or "",
                        c.node_type_id,
                        c.driver_node_type_id,
                        c.num_workers,
                        c.spark_version,
                        autosc.min_workers if autosc else None,
                        autosc.max_workers if autosc else None,
                        c.custom_tags,
                    )
            return ("", None, None, None, None, None, None, None)

        (
            existing_id,
            existing_node,
            existing_driver,
            existing_workers,
            existing_spark,
            existing_min,
            existing_max,
            existing_tags,
        ) = await asyncio.to_thread(_find_existing)

        if existing_id:
            mismatches: list[str] = []
            if existing_node != node_type:
                mismatches.append(f"node_type {existing_node} != {node_type}")
            if existing_driver != driver_node_type:
                mismatches.append(
                    f"driver_node_type {existing_driver} != {driver_node_type}"
                )
            if existing_spark != spark_version:
                mismatches.append(f"spark {existing_spark} != {spark_version}")

            if autoscale is not None:
                if (existing_min, existing_max) != autoscale:
                    mismatches.append(
                        f"autoscale ({existing_min},{existing_max}) != {autoscale}"
                    )
            else:
                if existing_workers != num_workers:
                    mismatches.append(
                        f"workers {existing_workers} != {num_workers}"
                    )

            existing_tags_map = existing_tags or {}
            if {k: existing_tags_map.get(k) for k in custom_tags} != custom_tags:
                mismatches.append("tags divergentes")

            if not mismatches:
                await ctx.info(
                    f"Cluster {cluster_name} ja existe e bate config: {existing_id}"
                )
                return existing_id, False

            await ctx.warn(
                f"Cluster {cluster_name} existe mas config divergente "
                f"({', '.join(mismatches)}). Reconfigurando via edit."
            )

            def _edit() -> None:
                w.clusters.edit(cluster_id=existing_id, **_build_kwargs())

            await asyncio.to_thread(_edit)
            await ctx.info(
                "Cluster reconfigurado (restart automatico, ~2min)"
            )
            # Edit nao "criou" — adopted+modified. Compensate NAO deve deletar.
            return existing_id, False

        sizing_label = (
            f"autoscale {autoscale[0]}-{autoscale[1]}"
            if autoscale
            else f"{num_workers} workers"
        )
        await ctx.info(
            f"Criando cluster {cluster_name} (driver={driver_node_type}, "
            f"worker={node_type}, {sizing_label}, DBR {spark_version})"
        )

        def _create() -> str:
            resp = w.clusters.create(**_build_kwargs())
            return resp.cluster_id or ""

        cluster_id = await asyncio.to_thread(_create)
        await ctx.info(f"Cluster criado: {cluster_id} (cold start ~2min)")
        return cluster_id, True
