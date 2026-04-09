"""Cria o Workflow Observer — agente AI autonomo que monitora falhas.

Uso: python deploy/create_observer_workflow.py

Requer env vars: DATABRICKS_HOST, DATABRICKS_TOKEN

O observer roda a cada 30 minutos, verifica se algum workflow
falhou na ultima hora, e aciona Claude Opus para diagnostico + PR.
Funciona com QUALQUER workflow do workspace.
"""

import os

from databricks.sdk import WorkspaceClient
from databricks.sdk.service.jobs import (
    CronSchedule,
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
                "Monitora workflows, detecta falhas, "
                "Claude Opus diagnostica e cria PR"
            ),
            **cluster_kwargs,
            notebook_task=NotebookTask(
                notebook_path=f"{repo_base}/notebooks/observer/collect_and_fix",
                base_parameters={
                    "scope": SECRET_SCOPE,
                    "workflow_name": "",  # vazio = todos
                    "hours": "1",
                },
            ),
            timeout_seconds=900,
        ),
    ]

    job = w.jobs.create(
        name="workflow_observer_agent",
        description=(
            "Agente AI autonomo que monitora todos os workflows "
            "do workspace. Detecta falhas, coleta contexto "
            "(codigo + logs + schema), chama Claude Opus para "
            "diagnostico e cria PR no GitHub com fix proposto."
        ),
        tasks=tasks,
        tags={
            "Project": "medallion-pipeline",
            "Team": "data-engineering",
            "Type": "observer-agent",
            "ManagedBy": "sdk",
        },
        schedule=CronSchedule(
            quartz_cron_expression="0 */30 * * * ?",  # a cada 30 min
            timezone_id="America/Sao_Paulo",
        ),
        max_concurrent_runs=1,
        timeout_seconds=900,
        email_notifications=JobEmailNotifications(
            on_failure=[ADMIN_EMAIL],
        ),
    )

    print(f"Observer criado!")
    print(f"  Job ID: {job.job_id}")
    print("  Nome: workflow_observer_agent")
    print("  Schedule: a cada 30 min")
    print("  Monitora: todos os workflows")

    return job.job_id


if __name__ == "__main__":
    job_id = create_observer()
    print(f"\nPara testar: python deploy/trigger_run.py {job_id}")
