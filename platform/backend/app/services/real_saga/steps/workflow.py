"""Step `workflow` — cria/atualiza o Databricks Job ETL do pipeline.

Porta a logica do `pipelines/pipeline-seguradora-whatsapp/deploy/create_workflow.py`
pro runner. O job tem 8 tasks (7 ETL em DAG + 1 observer_trigger sentinel) e
e executado diariamente via schedule cron.

A sentinel task depende de TODAS as tasks ETL com `run_if=AT_LEAST_ONE_FAILED`
— so dispara o Observer se alguma task falhou.
"""

from __future__ import annotations

from databricks.sdk.service.jobs import (
    CronSchedule,
    JobEmailNotifications,
    NotebookTask,
    RunIf,
    Task,
    TaskDependency,
)

from app.services.real_saga.base import StepContext
from app.services.real_saga.databricks_client import workspace_client
from app.services.real_saga.steps.observer import _upsert_job

WORKFLOW_JOB_NAME = "medallion_pipeline_whatsapp"


def _to_quartz_cron(cron: str) -> str:
    """Converte unix cron (5 campos) pra Quartz cron (6 campos).

    Unix:   minute hour dom month dow        (ex: '0 6 * * *')
    Quartz: second minute hour dom month dow (ex: '0 0 6 * * ?')
    """
    parts = cron.strip().split()
    if len(parts) == 5:
        # Unix -> Quartz: adiciona seconds=0 no inicio, troca dow '*' por '?'
        minute, hour, dom, month, dow = parts
        if dow == "*":
            dow = "?"
        return f"0 {minute} {hour} {dom} {month} {dow}"
    return cron  # ja esta em Quartz (6+ campos)


class WorkflowStep:
    step_id = "workflow"

    @staticmethod
    async def _auto_detect_cluster(ctx: StepContext) -> str:
        """Auto-detecta o primeiro cluster disponivel no workspace.

        Necessario porque serverless nao suporta spark.hadoop.fs.s3a.*
        que o S3Lake usa pra ler/escrever dados.
        """
        import asyncio

        w = workspace_client(ctx.credentials)

        def _find() -> str:
            clusters = list(w.clusters.list())
            if not clusters:
                return ""
            # Prefere cluster que ja esteja running ou que tenha "pipeline" no nome
            pipeline_cluster = next(
                (c for c in clusters if "pipeline" in (c.cluster_name or "").lower()), None
            )
            chosen = pipeline_cluster or clusters[0]
            return chosen.cluster_id or ""

        cluster_id = await asyncio.to_thread(_find)
        if cluster_id:
            await ctx.info(f"Cluster auto-detectado: {cluster_id}")
        else:
            await ctx.warn("Nenhum cluster encontrado — usando serverless (pode falhar com S3)")
        return cluster_id

    async def execute(self, ctx: StepContext) -> None:
        env = ctx.env_vars()
        catalog = env.get("catalog", ctx.shared.catalog or "medallion")
        scope = env.get("secret_scope", "medallion-pipeline")
        bronze_prefix = env.get("bronze_prefix", "bronze/")
        # O wizard pode enviar cron unix (5 campos) — converter pra Quartz (6 campos)
        raw_cron = env.get("schedule_cron", "0 0 6 * * ?")
        schedule_cron = _to_quartz_cron(raw_cron)
        admin_email = env.get("admin_email", "administrator@idlehub.com.br")

        repo_path = ctx.shared.repo_path
        if not repo_path:
            raise RuntimeError("workflow step sem repo_path — step `upload` deve rodar antes")

        observer_job_id = ctx.shared.observer_job_id
        if not observer_job_id:
            raise RuntimeError(
                "workflow step sem observer_job_id — step `observer` deve rodar antes"
            )

        cluster_id = env.get("cluster_id", "")
        if not cluster_id:
            cluster_id = await self._auto_detect_cluster(ctx)
        pipeline_notebooks = (
            f"{repo_path}/pipelines/pipeline-seguradora-whatsapp/notebooks"
        )
        observer_config_path = (
            f"/Workspace{repo_path}/pipelines/pipeline-seguradora-whatsapp/observer_config.yaml"
        )

        w = workspace_client(ctx.credentials)
        await ctx.info(f"Criando workflow '{WORKFLOW_JOB_NAME}' com 8 tasks")

        base_params: dict[str, str] = {
            "catalog": catalog,
            "scope": scope,
            "chaos_mode": "off",
            "bronze_prefix": bronze_prefix,
        }

        # Se cluster_id esta configurado, usa cluster dedicado (necessario pra
        # spark.hadoop.fs.s3a.* que nao funciona em serverless).
        # Se vazio, serverless auto-provisionado.
        cluster_kwarg = {"existing_cluster_id": cluster_id} if cluster_id else {}
        if cluster_id:
            await ctx.info(f"Usando cluster dedicado: {cluster_id}")

        tasks: list[Task] = [
            Task(
                task_key="pre_check",
                description="Pre-flight: propaga run_id + chaos_mode via task values",
                notebook_task=NotebookTask(
                    notebook_path=f"{pipeline_notebooks}/pre_check",
                    base_parameters=base_params,
                ),
                timeout_seconds=900,
                max_retries=1,
                **cluster_kwarg,
            ),
            Task(
                task_key="bronze_ingestion",
                description="S3 parquet -> Delta bronze.conversations (overwrite idempotente)",
                notebook_task=NotebookTask(
                    notebook_path=f"{pipeline_notebooks}/bronze/ingest",
                    base_parameters=base_params,
                ),
                depends_on=[TaskDependency(task_key="pre_check")],
                timeout_seconds=900,
                max_retries=2,
                **cluster_kwarg,
            ),
            Task(
                task_key="silver_dedup",
                description="Dedup sent+delivered + normalizacao",
                notebook_task=NotebookTask(
                    notebook_path=f"{pipeline_notebooks}/silver/dedup_clean",
                    base_parameters=base_params,
                ),
                depends_on=[TaskDependency(task_key="bronze_ingestion")],
                timeout_seconds=600,
                max_retries=2,
                **cluster_kwarg,
            ),
            Task(
                task_key="silver_entities",
                description="Entity extraction + masking HMAC + redaction",
                notebook_task=NotebookTask(
                    notebook_path=f"{pipeline_notebooks}/silver/entities_mask",
                    base_parameters=base_params,
                ),
                depends_on=[TaskDependency(task_key="silver_dedup")],
                timeout_seconds=900,
                max_retries=2,
                **cluster_kwarg,
            ),
            Task(
                task_key="silver_enrichment",
                description="Metricas conversacionais por chat",
                notebook_task=NotebookTask(
                    notebook_path=f"{pipeline_notebooks}/silver/enrichment",
                    base_parameters=base_params,
                ),
                depends_on=[TaskDependency(task_key="silver_dedup")],
                timeout_seconds=600,
                max_retries=2,
                **cluster_kwarg,
            ),
            Task(
                task_key="gold_analytics",
                description="12 notebooks analiticos em paralelo",
                notebook_task=NotebookTask(
                    notebook_path=f"{pipeline_notebooks}/gold/analytics",
                    base_parameters=base_params,
                ),
                depends_on=[
                    TaskDependency(task_key="silver_entities"),
                    TaskDependency(task_key="silver_enrichment"),
                ],
                timeout_seconds=1800,
                max_retries=1,
                **cluster_kwarg,
            ),
            Task(
                task_key="quality_validation",
                description="Row counts, null rates, consistency checks",
                notebook_task=NotebookTask(
                    notebook_path=f"{pipeline_notebooks}/validation/checks",
                    base_parameters=base_params,
                ),
                depends_on=[TaskDependency(task_key="gold_analytics")],
                timeout_seconds=300,
                max_retries=1,
                **cluster_kwarg,
            ),
            Task(
                task_key="observer_trigger",
                description="Sentinel — dispara Observer Agent so se alguma task acima falhou",
                notebook_task=NotebookTask(
                    notebook_path=f"{repo_path}/observer-framework/notebooks/trigger_sentinel",
                    base_parameters={
                        "catalog": catalog,
                        "scope": scope,
                        "observer_job_id": str(observer_job_id),
                        "llm_provider": "anthropic",
                        "git_provider": "github",
                        "observer_config_path": observer_config_path,
                    },
                ),
                depends_on=[
                    TaskDependency(task_key="pre_check"),
                    TaskDependency(task_key="bronze_ingestion"),
                    TaskDependency(task_key="silver_dedup"),
                    TaskDependency(task_key="silver_entities"),
                    TaskDependency(task_key="silver_enrichment"),
                    TaskDependency(task_key="gold_analytics"),
                    TaskDependency(task_key="quality_validation"),
                ],
                run_if=RunIf.AT_LEAST_ONE_FAILED,
                timeout_seconds=300,
                max_retries=0,
                **cluster_kwarg,
            ),
        ]

        settings = {
            "name": WORKFLOW_JOB_NAME,
            "description": (
                "Medallion WhatsApp — Bronze -> Silver -> Gold com Observer sentinel.\n"
                "Overwrite idempotente em cada camada (Delta atomic commits)."
            ),
            "tasks": tasks,
            "tags": {
                "Project": "medallion-pipeline",
                "Team": "data-engineering",
                "Environment": ctx.deployment.environment,
                "Type": "etl-pipeline",
                "CompanyId": str(ctx.company_id),
            },
            "schedule": CronSchedule(
                quartz_cron_expression=schedule_cron,
                timezone_id="America/Sao_Paulo",
            ),
            "max_concurrent_runs": 1,
            "timeout_seconds": 3600,
            "email_notifications": JobEmailNotifications(
                on_failure=[admin_email],
                on_start=[admin_email],
            ),
        }

        job_id = await _upsert_job(w, WORKFLOW_JOB_NAME, settings)
        await ctx.success(f"Pipeline workflow pronto: id={job_id}")
        ctx.shared.workflow_job_id = job_id
