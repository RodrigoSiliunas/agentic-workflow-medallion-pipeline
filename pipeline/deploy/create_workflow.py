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
    WebhookNotifications,
)

# ============================================================
# CONFIGURACAO — env vars com defaults sensatos
# ============================================================
ADMIN_EMAIL = os.environ.get("PIPELINE_ADMIN_EMAIL", "administrator@idlehub.com.br")
CATALOG = os.environ.get("PIPELINE_CATALOG", "medallion")
SECRET_SCOPE = os.environ.get("PIPELINE_SECRET_SCOPE", "medallion-pipeline")


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
    shared_params = {
        "catalog": CATALOG,
        "scope": SECRET_SCOPE,
    }

    # ============================================================
    # TASKS — Medallion Pipeline (Bronze → Silver → Gold)
    # ============================================================
    tasks = [
        Task(
            task_key="agent_pre",
            description="Pre-check: fingerprint S3, captura versoes Delta, decide se processa",
            notebook_task=NotebookTask(
                notebook_path=nb("agent_pre"),
                base_parameters={**shared_params, "bronze_prefix": "bronze/"},
            ),
            max_retries=1,
            timeout_seconds=300,  # 5 min
        ),
        Task(
            task_key="bronze_ingestion",
            description="Ingestao: S3 parquet → Delta Table bronze.conversations",
            depends_on=[TaskDependency(task_key="agent_pre")],
            notebook_task=NotebookTask(
                notebook_path=nb("bronze/ingest"),
                base_parameters={**shared_params, "bronze_prefix": "bronze/"},
            ),
            max_retries=2,
            timeout_seconds=600,  # 10 min
        ),
        Task(
            task_key="silver_dedup",
            description="Dedup + Clean: remove sent+delivered duplicados, normaliza nomes",
            depends_on=[TaskDependency(task_key="bronze_ingestion")],
            notebook_task=NotebookTask(
                notebook_path=nb("silver/dedup_clean"),
                base_parameters=shared_params,
            ),
            max_retries=2,
            timeout_seconds=600,
        ),
        Task(
            task_key="silver_entities",
            description="Entity extraction (CPF/email/phone/plate) + masking + redaction",
            depends_on=[TaskDependency(task_key="silver_dedup")],
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
            notebook_task=NotebookTask(
                notebook_path=nb("silver/enrichment"),
                base_parameters=shared_params,
            ),
            max_retries=2,
            timeout_seconds=600,
        ),
        Task(
            task_key="gold_analytics",
            description="12 notebooks analiticos: funnel, sentiment, lead scoring, etc.",
            depends_on=[
                TaskDependency(task_key="silver_entities"),
                TaskDependency(task_key="silver_enrichment"),
            ],
            notebook_task=NotebookTask(
                notebook_path=nb("gold/analytics"),
                base_parameters=shared_params,
            ),
            max_retries=1,
            timeout_seconds=1800,  # 30 min (12 sub-notebooks)
        ),
        Task(
            task_key="quality_validation",
            description="Quality checks: row counts, null rates, cross-layer consistency",
            depends_on=[TaskDependency(task_key="gold_analytics")],
            notebook_task=NotebookTask(
                notebook_path=nb("validation/checks"),
                base_parameters=shared_params,
            ),
            max_retries=1,
            timeout_seconds=300,
        ),
        Task(
            task_key="agent_post",
            description="Post-check: recovery, rollback Delta, AI diagnosis, notifications",
            depends_on=[TaskDependency(task_key="quality_validation")],
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
            "Pipeline Medallion agentico para analise de conversas WhatsApp de seguro auto.\n\n"
            "Fluxo: agent_pre → bronze (ingestao S3) → silver (dedup + entities/masking + enrichment) "
            "→ gold (12 tabelas analiticas) → validation → agent_post (recovery + notifications).\n\n"
            "Dados persistem em S3 (data lake) e Unity Catalog (queries SQL).\n"
            "Acesso S3 via boto3 + Databricks Secrets (multi-tenant ready)."
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
        health={
            "rules": [
                {
                    "metric": "RUN_DURATION_SECONDS",
                    "op": "GREATER_THAN",
                    "value": 2400,  # Warning se > 40 min
                },
            ],
        },
    )

    print("Workflow criado com sucesso!")
    print(f"  Job ID:      {job.job_id}")
    print(f"  Nome:        medallion_pipeline_whatsapp")
    print(f"  Admin:       {ADMIN_EMAIL}")
    print(f"  Catalog:     {CATALOG}")
    print(f"  Scope:       {SECRET_SCOPE}")
    print(f"  Timeout:     3600s (job) + per-task")
    print(f"  Schedule:    06:00 diario (Sao Paulo)")
    print(f"  Tags:        Project, Team, CostCenter, Environment, DataDomain")
    print(f"  Alerts:      on_start + on_failure + duration_warning > 40min")
    print(f"  Tasks:       {len(tasks)}")

    return job.job_id


if __name__ == "__main__":
    job_id = create_workflow()
    print(f"\nPara executar: python deploy/trigger_run.py {job_id}")
