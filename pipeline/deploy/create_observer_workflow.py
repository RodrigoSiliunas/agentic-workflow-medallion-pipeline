"""Cria o Observer Agent — agente AI independente.

Triggered sob demanda quando um pipeline falha.
Nao tem schedule — eh acionado via SDK pelo pipeline ETL
ou manualmente pelo trigger_run.py.

Uso: python deploy/create_observer_workflow.py
"""

import os

from databricks.sdk import WorkspaceClient
from databricks.sdk.service.jobs import (
    JobEmailNotifications,
    NotebookTask,
    Task,
)

ADMIN_EMAIL = os.environ.get(
    "PIPELINE_ADMIN_EMAIL", "administrator@idlehub.com.br"
)
SECRET_SCOPE = os.environ.get(
    "PIPELINE_SECRET_SCOPE", "medallion-pipeline"
)
CLUSTER_ID = os.environ.get("PIPELINE_CLUSTER_ID", "")


def create_observer():
    w = WorkspaceClient(
        host=os.environ["DATABRICKS_HOST"],
        token=os.environ["DATABRICKS_TOKEN"],
    )

    user = w.current_user.me()
    print(f"Conectado como: {user.user_name}")

    repo_base = (
        f"/Repos/{user.user_name}"
        "/agentic-workflow-medallion-pipeline/pipeline"
    )

    cluster_kwargs = {}
    if CLUSTER_ID:
        cluster_kwargs["existing_cluster_id"] = CLUSTER_ID

    tasks = [
        Task(
            task_key="observe_and_fix",
            description=(
                "Coleta erro + codigo via API, "
                "Claude Opus diagnostica, cria PR"
            ),
            **cluster_kwargs,
            notebook_task=NotebookTask(
                notebook_path=(
                    f"{repo_base}/notebooks/observer/collect_and_fix"
                ),
                base_parameters={
                    "scope": SECRET_SCOPE,
                    "source_run_id": "",
                    "source_job_id": "",
                },
            ),
            timeout_seconds=900,
        ),
    ]

    job = w.jobs.create(
        name="workflow_observer_agent",
        description=(
            "Agente AI autonomo. Triggered por pipelines que "
            "falharam. Coleta codigo via Workspace API, chama "
            "Claude Opus para diagnostico e cria PR no GitHub.\n"
            "Generico — funciona com qualquer workflow."
        ),
        tasks=tasks,
        tags={
            "Project": "medallion-pipeline",
            "Team": "data-engineering",
            "Type": "observer-agent",
        },
        # Sem schedule — triggered sob demanda
        max_concurrent_runs=3,
        timeout_seconds=900,
        email_notifications=JobEmailNotifications(
            on_failure=[ADMIN_EMAIL],
        ),
    )

    print("Observer criado!")
    print(f"  Job ID: {job.job_id}")
    print("  Nome: workflow_observer_agent")
    print("  Schedule: nenhum (triggered sob demanda)")
    print("  Max concurrent: 3")

    return job.job_id


if __name__ == "__main__":
    job_id = create_observer()
    print(f"\nPara testar: python deploy/trigger_run.py {job_id}")
