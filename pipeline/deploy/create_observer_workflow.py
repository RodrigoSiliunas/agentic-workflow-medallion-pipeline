"""Cria o workflow do Observer Agent.

Triggered sob demanda quando um pipeline falha.
Nao tem schedule - e acionado via SDK pelo task sentinel do ETL
ou manualmente para debug.

Uso: python deploy/create_observer_workflow.py
"""

import os

from databricks.sdk import WorkspaceClient
from databricks.sdk.service.jobs import (
    JobEmailNotifications,
    JobSettings,
    NotebookTask,
    Task,
)

ADMIN_EMAIL = os.environ.get(
    "PIPELINE_ADMIN_EMAIL", "administrator@idlehub.com.br"
)
CATALOG = os.environ.get("PIPELINE_CATALOG", "medallion")
SECRET_SCOPE = os.environ.get(
    "PIPELINE_SECRET_SCOPE", "medallion-pipeline"
)
CLUSTER_ID = os.environ.get("PIPELINE_CLUSTER_ID", "")
WORKFLOW_NAME = "workflow_observer_agent"


def find_latest_job_id(workspace: WorkspaceClient, name: str) -> int | None:
    """Retorna o job_id mais alto para um dado nome."""
    jobs = list(workspace.jobs.list(name=name))
    if not jobs:
        return None
    return max(int(job.job_id) for job in jobs if getattr(job, "job_id", None) is not None)


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
                    "catalog": CATALOG,
                    "scope": SECRET_SCOPE,
                    "source_run_id": "",
                    "source_job_id": "",
                    "source_job_name": "",
                    "failed_tasks": "[]",
                    "llm_provider": "anthropic",
                    "git_provider": "github",
                    "dedup_window_hours": "24",
                },
            ),
            timeout_seconds=900,
        ),
    ]

    job_settings = JobSettings(
        name=WORKFLOW_NAME,
        description=(
            "Agente AI autonomo. Triggered por pipelines que "
            "falharam. Coleta codigo via Workspace API, chama "
            "Claude Opus para diagnostico e cria PR no GitHub.\n"
            "Generico - funciona com qualquer workflow."
        ),
        tasks=tasks,
        tags={
            "Project": "medallion-pipeline",
            "Team": "data-engineering",
            "Type": "observer-agent",
        },
        max_concurrent_runs=3,
        timeout_seconds=900,
        email_notifications=JobEmailNotifications(
            on_failure=[ADMIN_EMAIL],
        ),
    )

    existing_job_id = find_latest_job_id(w, WORKFLOW_NAME)
    if existing_job_id is not None:
        w.jobs.reset(job_id=existing_job_id, new_settings=job_settings)
        job_id = existing_job_id
        action = "Observer atualizado"
    else:
        job = w.jobs.create(**job_settings.as_dict())
        job_id = job.job_id
        action = "Observer criado"

    print(f"{action}!")
    print(f"  Job ID: {job_id}")
    print(f"  Nome: {WORKFLOW_NAME}")
    print("  Schedule: nenhum (triggered sob demanda)")
    print("  Max concurrent: 3")

    return job_id


if __name__ == "__main__":
    job_id = create_observer()
    print(f"\nPara testar: python deploy/trigger_run.py {job_id}")
