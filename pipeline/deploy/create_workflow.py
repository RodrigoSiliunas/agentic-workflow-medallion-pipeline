"""Cria o Databricks Workflow 'medallion_pipeline' via SDK.

Uso: python deploy/create_workflow.py

Requer env vars: DATABRICKS_HOST, DATABRICKS_TOKEN

O workflow usa serverless compute com parametros passados via widgets.
Cada task recebe base_parameters que preenchem os dbutils.widgets dos notebooks.
"""

import os

from databricks.sdk import WorkspaceClient
from databricks.sdk.service.jobs import (
    CronSchedule,
    JobEmailNotifications,
    NotebookTask,
    RunIf,
    Task,
    TaskDependency,
)

# ============================================================
# CONFIGURACAO — env vars com defaults sensatos
# ============================================================
ADMIN_EMAIL = os.environ.get("PIPELINE_ADMIN_EMAIL", "administrator@idlehub.com.br")
CATALOG = os.environ.get("PIPELINE_CATALOG", "medallion")
SECRET_SCOPE = os.environ.get("PIPELINE_SECRET_SCOPE", "medallion-pipeline")
CLUSTER_ID = os.environ.get("PIPELINE_CLUSTER_ID", "")


def create_workflow():
    w = WorkspaceClient(
        host=os.environ["DATABRICKS_HOST"],
        token=os.environ["DATABRICKS_TOKEN"],
    )

    user = w.current_user.me()
    print(f"Conectado como: {user.user_name}")

    # Auto-detect repo path based on current user
    repo_path = f"/Repos/{user.user_name}/agentic-workflow-medallion-pipeline/pipeline"

    def nb(name: str) -> str:
        return f"{repo_path}/notebooks/{name}"

    # Parametros compartilhados por todas as tasks
    # chaos_mode: off por padrao, ativado via trigger_chaos.py
    shared_params = {
        "catalog": CATALOG,
        "scope": SECRET_SCOPE,
        "chaos_mode": "off",
    }

    # Cluster: se PIPELINE_CLUSTER_ID definido, usa cluster existente
    # Caso contrario, roda em serverless
    cluster_kwargs = {}
    if CLUSTER_ID:
        cluster_kwargs["existing_cluster_id"] = CLUSTER_ID
        print(f"  Cluster: {CLUSTER_ID}")
    else:
        print("  Compute: serverless")

    # ============================================================
    # TASKS — Medallion Pipeline (Bronze > Silver > Gold)
    # ============================================================
    tasks = [
        Task(
            task_key="agent_pre",
            description="Pre-check: fingerprint S3, captura versoes Delta",
            **cluster_kwargs,
            notebook_task=NotebookTask(
                notebook_path=nb("agent_pre"),
                base_parameters={**shared_params, "bronze_prefix": "bronze/"},
            ),
            max_retries=1,
            timeout_seconds=600,  # 10 min (inclui cold start)
        ),
        Task(
            task_key="bronze_ingestion",
            description="Ingestao: S3 parquet -> Delta bronze.conversations",
            depends_on=[TaskDependency(task_key="agent_pre")],
            **cluster_kwargs,
            notebook_task=NotebookTask(
                notebook_path=nb("bronze/ingest"),
                base_parameters={**shared_params, "bronze_prefix": "bronze/"},
            ),
            max_retries=2,
            timeout_seconds=600,  # 10 min
        ),
        Task(
            task_key="silver_dedup",
            description="Dedup + Clean: remove duplicados, normaliza nomes",
            depends_on=[TaskDependency(task_key="bronze_ingestion")],
            **cluster_kwargs,
            notebook_task=NotebookTask(
                notebook_path=nb("silver/dedup_clean"),
                base_parameters=shared_params,
            ),
            max_retries=2,
            timeout_seconds=600,
        ),
        Task(
            task_key="silver_entities",
            description="Entity extraction + masking + redaction",
            depends_on=[TaskDependency(task_key="silver_dedup")],
            **cluster_kwargs,
            notebook_task=NotebookTask(
                notebook_path=nb("silver/entities_mask"),
                base_parameters=shared_params,
            ),
            max_retries=2,
            timeout_seconds=900,  # 15 min (masking é pesado)
        ),
        Task(
            task_key="silver_enrichment",
            description="Metricas por conversa: duracao, mensagens, response time",
            depends_on=[TaskDependency(task_key="silver_dedup")],
            **cluster_kwargs,
            notebook_task=NotebookTask(
                notebook_path=nb("silver/enrichment"),
                base_parameters=shared_params,
            ),
            max_retries=2,
            timeout_seconds=600,
        ),
        Task(
            task_key="gold_analytics",
            description="12 notebooks analiticos sequenciais",
            depends_on=[
                TaskDependency(task_key="silver_entities"),
                TaskDependency(task_key="silver_enrichment"),
            ],
            **cluster_kwargs,
            notebook_task=NotebookTask(
                notebook_path=nb("gold/analytics"),
                base_parameters=shared_params,
            ),
            max_retries=1,
            timeout_seconds=1800,  # 30 min (12 sub-notebooks)
        ),
        Task(
            task_key="quality_validation",
            description="Quality checks: row counts, null rates, consistency",
            depends_on=[TaskDependency(task_key="gold_analytics")],
            **cluster_kwargs,
            notebook_task=NotebookTask(
                notebook_path=nb("validation/checks"),
                base_parameters=shared_params,
            ),
            max_retries=1,
            timeout_seconds=300,
        ),
        Task(
            task_key="agent_post",
            description="Post-check: recovery, rollback, AI diagnosis",
            depends_on=[TaskDependency(task_key="quality_validation")],
            **cluster_kwargs,
            notebook_task=NotebookTask(
                notebook_path=nb("agent_post"),
                base_parameters=shared_params,
            ),
            max_retries=0,  # Guardrail: nunca retentar
            run_if=RunIf.ALL_DONE,
            timeout_seconds=600,
        ),
    ]

    # ============================================================
    # CRIAR O JOB
    # ============================================================
    job = w.jobs.create(
        name="medallion_pipeline_whatsapp",
        description=(
            "Pipeline Medallion agentico para analise de conversas "
            "WhatsApp de seguro auto.\n\n"
            "Fluxo: agent_pre > bronze > silver (dedup + entities "
            "+ enrichment) > gold (12 tabelas) > validation > "
            "agent_post (recovery + notifications).\n\n"
            "Dados em S3 (lake) e Unity Catalog (queries SQL).\n"
            "S3 via boto3 + Databricks Secrets (multi-tenant)."
        ),
        tasks=tasks,
        tags={
            "Project": "medallion-pipeline",
            "Team": "data-engineering",
            "CostCenter": "pipeline-001",
            "Environment": "production",
            "DataDomain": "whatsapp-insurance",
            "ManagedBy": "sdk",
        },
        schedule=CronSchedule(
            quartz_cron_expression="0 0 6 * * ?",
            timezone_id="America/Sao_Paulo",
        ),
        max_concurrent_runs=1,
        timeout_seconds=3600,  # 1h max para o job inteiro
        email_notifications=JobEmailNotifications(
            on_failure=[ADMIN_EMAIL],
            on_start=[ADMIN_EMAIL],
            on_duration_warning_threshold_exceeded=[ADMIN_EMAIL],
        ),
        # health rules removed — SDK requires typed objects, configure via UI
    )

    print("Workflow criado com sucesso!")
    print(f"  Job ID:      {job.job_id}")
    print("  Nome:        medallion_pipeline_whatsapp")
    print(f"  Admin:       {ADMIN_EMAIL}")
    print(f"  Catalog:     {CATALOG}")
    print(f"  Scope:       {SECRET_SCOPE}")
    print("  Timeout:     3600s (job) + per-task")
    print("  Schedule:    06:00 diario (Sao Paulo)")
    print("  Tags:        Project, Team, CostCenter, Environment")
    print("  Alerts:      on_start + on_failure + duration_warning")
    print(f"  Tasks:       {len(tasks)}")

    return job.job_id


if __name__ == "__main__":
    job_id = create_workflow()
    print(f"\nPara executar: python deploy/trigger_run.py {job_id}")
