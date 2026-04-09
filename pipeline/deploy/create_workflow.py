"""Cria o Databricks Workflow 'medallion_pipeline' via SDK.

Uso: python deploy/create_workflow.py

Requer env vars: DATABRICKS_HOST, DATABRICKS_TOKEN
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
# CONFIGURACAO
# ============================================================
REPO_PATH = "/Repos/rodrigosiliunas1@gmail.com/agentic-workflow-medallion-pipeline/pipeline"
EMAIL = "rodrigosiliunas1@gmail.com"


def notebook_path(name: str) -> str:
    return f"{REPO_PATH}/notebooks/{name}"


def create_workflow():
    w = WorkspaceClient(
        host=os.environ["DATABRICKS_HOST"],
        token=os.environ["DATABRICKS_TOKEN"],
    )

    print(f"Conectado como: {w.current_user.me().user_name}")

    # ============================================================
    # DEFINIR TASKS DO WORKFLOW
    # ============================================================
    tasks = [
        # Task 0: Agent Pre-Check
        Task(
            task_key="agent_pre",
            notebook_task=NotebookTask(notebook_path=notebook_path("agent_pre")),
            max_retries=1,
        ),
        # Task 1: Bronze Ingestion
        Task(
            task_key="bronze_ingestion",
            depends_on=[TaskDependency(task_key="agent_pre")],
            notebook_task=NotebookTask(notebook_path=notebook_path("bronze/ingest")),
            max_retries=2,
        ),
        # Task 2a: Silver Dedup + Clean
        Task(
            task_key="silver_dedup",
            depends_on=[TaskDependency(task_key="bronze_ingestion")],
            notebook_task=NotebookTask(notebook_path=notebook_path("silver/dedup_clean")),
            max_retries=2,
        ),
        # Task 2b: Silver Entities + Mask (paralela com 2c)
        Task(
            task_key="silver_entities",
            depends_on=[TaskDependency(task_key="silver_dedup")],
            notebook_task=NotebookTask(notebook_path=notebook_path("silver/entities_mask")),
            max_retries=2,
        ),
        # Task 2c: Silver Enrichment (paralela com 2b)
        Task(
            task_key="silver_enrichment",
            depends_on=[TaskDependency(task_key="silver_dedup")],
            notebook_task=NotebookTask(notebook_path=notebook_path("silver/enrichment")),
            max_retries=2,
        ),
        # Task 3: Gold Analytics
        Task(
            task_key="gold_analytics",
            depends_on=[
                TaskDependency(task_key="silver_entities"),
                TaskDependency(task_key="silver_enrichment"),
            ],
            notebook_task=NotebookTask(notebook_path=notebook_path("gold/analytics")),
            max_retries=2,
        ),
        # Task 4: Quality Validation
        Task(
            task_key="quality_validation",
            depends_on=[TaskDependency(task_key="gold_analytics")],
            notebook_task=NotebookTask(notebook_path=notebook_path("validation/checks")),
            max_retries=1,
        ),
        # Task 5: Agent Post-Check (roda SEMPRE)
        Task(
            task_key="agent_post",
            depends_on=[TaskDependency(task_key="quality_validation")],
            notebook_task=NotebookTask(notebook_path=notebook_path("agent_post")),
            max_retries=0,  # Guardrail: nao retentar
            run_if=RunIf.ALL_DONE,
        ),
    ]

    # ============================================================
    # CRIAR O JOB
    # ============================================================
    job = w.jobs.create(
        name="medallion_pipeline_whatsapp",
        tasks=tasks,
        schedule=CronSchedule(
            quartz_cron_expression="0 0 6 * * ?",  # 06:00 UTC diario
            timezone_id="America/Sao_Paulo",
        ),
        max_concurrent_runs=1,
        email_notifications=JobEmailNotifications(
            on_failure=[EMAIL],
        ),
    )

    print("Workflow criado com sucesso!")
    print(f"  Job ID: {job.job_id}")
    print("  Nome: medallion_pipeline_whatsapp")
    print("  Schedule: 06:00 diario (America/Sao_Paulo)")
    print(f"  Tasks: {len(tasks)}")
    print("  max_concurrent_runs: 1")
    print(f"  Email on failure: {EMAIL}")

    return job.job_id


if __name__ == "__main__":
    job_id = create_workflow()
    print(f"\nPara executar manualmente: python deploy/trigger_run.py {job_id}")
