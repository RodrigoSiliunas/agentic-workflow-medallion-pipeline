"""Cria o Databricks Workflow ETL Medallion.

Pipeline puro de dados: Bronze > Silver > Gold > Validation.
Sem logica de agente — o Observer Agent roda separado.

Uso: python deploy/create_workflow.py

Requer env vars: DATABRICKS_HOST, DATABRICKS_TOKEN
Opcionais: PIPELINE_CLUSTER_ID, PIPELINE_ADMIN_EMAIL,
           PIPELINE_CATALOG, PIPELINE_SECRET_SCOPE
"""

import os

from databricks.sdk import WorkspaceClient
from databricks.sdk.service.jobs import (
    CronSchedule,
    JobEmailNotifications,
    NotebookTask,
    Task,
    TaskDependency,
)

ADMIN_EMAIL = os.environ.get(
    "PIPELINE_ADMIN_EMAIL", "administrator@idlehub.com.br"
)
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

    repo_path = (
        f"/Repos/{user.user_name}"
        "/agentic-workflow-medallion-pipeline/pipeline"
    )

    def nb(name: str) -> str:
        return f"{repo_path}/notebooks/{name}"

    shared_params = {
        "catalog": CATALOG,
        "scope": SECRET_SCOPE,
        "chaos_mode": "off",
    }

    cluster_kwargs = {}
    if CLUSTER_ID:
        cluster_kwargs["existing_cluster_id"] = CLUSTER_ID
        print(f"  Cluster: {CLUSTER_ID}")
    else:
        print("  Compute: serverless")

    # =========================================================
    # TASKS — ETL puro (Bronze > Silver > Gold > Validation)
    # Sem agente — Observer cuida de falhas separadamente
    # =========================================================
    tasks = [
        Task(
            task_key="bronze_ingestion",
            description="S3 parquet -> Delta bronze.conversations",
            **cluster_kwargs,
            notebook_task=NotebookTask(
                notebook_path=nb("bronze/ingest"),
                base_parameters={
                    **shared_params,
                    "bronze_prefix": "bronze/",
                },
            ),
            max_retries=2,
            timeout_seconds=900,
        ),
        Task(
            task_key="silver_dedup",
            description="Dedup sent+delivered, normaliza nomes",
            depends_on=[
                TaskDependency(task_key="bronze_ingestion"),
            ],
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
            depends_on=[
                TaskDependency(task_key="silver_dedup"),
            ],
            **cluster_kwargs,
            notebook_task=NotebookTask(
                notebook_path=nb("silver/entities_mask"),
                base_parameters=shared_params,
            ),
            max_retries=2,
            timeout_seconds=900,
        ),
        Task(
            task_key="silver_enrichment",
            description="Metricas por conversa",
            depends_on=[
                TaskDependency(task_key="silver_dedup"),
            ],
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
            description="12 notebooks analiticos",
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
            timeout_seconds=1800,
        ),
        Task(
            task_key="quality_validation",
            description="Row counts, null rates, consistency",
            depends_on=[
                TaskDependency(task_key="gold_analytics"),
            ],
            **cluster_kwargs,
            notebook_task=NotebookTask(
                notebook_path=nb("validation/checks"),
                base_parameters=shared_params,
            ),
            max_retries=1,
            timeout_seconds=300,
        ),
    ]

    job = w.jobs.create(
        name="medallion_pipeline_whatsapp",
        description=(
            "Pipeline ETL Medallion: Bronze > Silver > Gold.\n"
            "Overwrite idempotente. Delta atomicity por task.\n"
            "Observer Agent monitora falhas separadamente."
        ),
        tasks=tasks,
        tags={
            "Project": "medallion-pipeline",
            "Team": "data-engineering",
            "CostCenter": "pipeline-001",
            "Environment": "production",
            "Type": "etl-pipeline",
        },
        schedule=CronSchedule(
            quartz_cron_expression="0 0 6 * * ?",
            timezone_id="America/Sao_Paulo",
        ),
        max_concurrent_runs=1,
        timeout_seconds=3600,
        email_notifications=JobEmailNotifications(
            on_failure=[ADMIN_EMAIL],
            on_start=[ADMIN_EMAIL],
        ),
    )

    print("Workflow criado!")
    print(f"  Job ID:   {job.job_id}")
    print("  Nome:     medallion_pipeline_whatsapp")
    print(f"  Tasks:    {len(tasks)}")
    print(f"  Admin:    {ADMIN_EMAIL}")

    return job.job_id


if __name__ == "__main__":
    job_id = create_workflow()
    print(f"\nPara executar: python deploy/trigger_run.py {job_id}")
