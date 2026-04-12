"""Step `observer` — cria/atualiza o Databricks Job do Observer Agent.

O Observer e um job on-demand (sem schedule) com 1 task que roda o notebook
`observer-framework/notebooks/collect_and_fix`. Ele e disparado pela sentinel
task do pipeline principal (step `workflow`) quando uma task ETL falha.

Este step roda ANTES do `workflow` step pra que o workflow possa usar o
`observer_job_id` como parametro da sentinel task.
"""

from __future__ import annotations

import asyncio

from databricks.sdk.service.jobs import (
    JobEmailNotifications,
    NotebookTask,
    Task,
)

from app.services.real_saga.base import StepContext
from app.services.real_saga.databricks_client import workspace_client

OBSERVER_JOB_NAME = "workflow_observer_agent"


class ObserverStep:
    step_id = "observer"

    async def execute(self, ctx: StepContext) -> None:
        env = ctx.env_vars()
        catalog = env.get("catalog", "medallion")
        scope = env.get("secret_scope", "medallion-pipeline")
        admin_email = env.get("admin_email", "administrator@idlehub.com.br")

        repo_path = ctx.shared.repo_path
        if not repo_path:
            raise RuntimeError(
                "observer step sem repo_path — o step `upload` deve rodar antes"
            )

        w = workspace_client(ctx.credentials)
        notebook = f"{repo_path}/observer-framework/notebooks/collect_and_fix"

        await ctx.info(f"Criando Observer job apontando pra {notebook}")

        tasks = [
            Task(
                task_key="observe_and_fix",
                description="Coleta contexto da falha via API e cria PR com diagnostico",
                notebook_task=NotebookTask(
                    notebook_path=notebook,
                    base_parameters={
                        "catalog": catalog,
                        "scope": scope,
                        "source_run_id": "",
                        "source_job_id": "",
                        "source_job_name": "",
                        "failed_tasks": "[]",
                        "llm_provider": "anthropic",
                        "git_provider": "github",
                        "dedup_window_hours": "24",
                        "dry_run": "false",
                    },
                ),
                timeout_seconds=900,
                max_retries=0,
            )
        ]

        settings = {
            "name": OBSERVER_JOB_NAME,
            "description": "Observer Agent — diagnostico autonomo de falhas do pipeline",
            "tasks": tasks,
            "tags": {
                "Project": "medallion-pipeline",
                "Type": "observer-agent",
                "CompanyId": str(ctx.company_id),
            },
            "max_concurrent_runs": 3,
            "timeout_seconds": 900,
            "email_notifications": JobEmailNotifications(
                on_failure=[admin_email],
            ),
        }

        job_id = await _upsert_job(w, OBSERVER_JOB_NAME, settings)
        await ctx.success(f"Observer job pronto: id={job_id}")
        ctx.shared.observer_job_id = job_id


async def _upsert_job(w, name: str, settings: dict) -> int:
    """Cria ou atualiza um job no Databricks.

    Se ja existe um job com o mesmo nome, deleta e recria (mais simples que
    reset, que exige JobSettings object em vez de dict kwargs).
    """

    def _do() -> int:
        existing_id: int | None = None
        for job in w.jobs.list(name=name):
            if existing_id is None or (job.job_id and job.job_id > existing_id):
                existing_id = job.job_id

        if existing_id is not None:
            w.jobs.delete(job_id=existing_id)

        created = w.jobs.create(**settings)
        return created.job_id

    return await asyncio.to_thread(_do)
