# Databricks notebook source
# MAGIC %md
# MAGIC # Observer Trigger Sentinel
# MAGIC Aguarda a conclusao do workflow ETL, identifica se houve falha real nas tasks
# MAGIC upstream e dispara o job do Observer automaticamente com o `source_run_id`
# MAGIC e metadados suficientes para diagnostico.
# MAGIC
# MAGIC **Camada:** Observer | **Dependencia:** todas as tasks do workflow ETL
# MAGIC **run_if:** `AT_LEAST_ONE_FAILED`
# MAGIC
# MAGIC _Ultima atualizacao: 2026-04-09_

# COMMAND ----------

# DBTITLE 1,Imports e Setup
import logging
import os
import sys

from databricks.sdk import WorkspaceClient

_nb_path = dbutils.notebook.entry_point.getDbutils().notebook().getContext().notebookPath().get()
_repo_root = "/".join(_nb_path.split("/")[:4])
PIPELINE_ROOT = f"/Workspace{_repo_root}/pipeline"
sys.path.insert(0, PIPELINE_ROOT)

from pipeline_lib.agent.observer import (
    OBSERVER_JOB_NAME,
    build_observer_notebook_params,
    extract_failed_task_keys,
    resolve_runtime_context,
)

logger = logging.getLogger("observer.trigger_sentinel")

# COMMAND ----------

# DBTITLE 1,Parametros
dbutils.widgets.text("catalog", "medallion", "Catalog Name")
dbutils.widgets.text("scope", "medallion-pipeline", "Secret Scope")
dbutils.widgets.text("observer_job_id", "", "Observer Job ID")
dbutils.widgets.text("llm_provider", "anthropic", "LLM Provider")
dbutils.widgets.text("git_provider", "github", "Git Provider")

CATALOG = dbutils.widgets.get("catalog")
SCOPE = dbutils.widgets.get("scope")
OBSERVER_JOB_ID = dbutils.widgets.get("observer_job_id").strip()
LLM_PROVIDER = dbutils.widgets.get("llm_provider").strip() or "anthropic"
GIT_PROVIDER = dbutils.widgets.get("git_provider").strip() or "github"

# COMMAND ----------

# DBTITLE 1,Helpers de Contexto do Databricks
def collect_context_tags() -> dict[str, str]:
    """Le apenas as tags necessarias do notebook context atual."""
    context = dbutils.notebook.entry_point.getDbutils().notebook().getContext()
    raw_tags = context.tags()
    tags: dict[str, str] = {}

    for key in ["jobId", "jobName", "jobRunId", "multitaskParentRunId", "runId", "taskKey"]:
        try:
            tags[key] = str(raw_tags.apply(key))
        except Exception:
            continue

    return tags


def resolve_current_run_id() -> int | None:
    """Recupera o run_id da task atual quando disponivel."""
    try:
        return int(
            dbutils.notebook.entry_point.getDbutils()
            .notebook()
            .getContext()
            .currentRunId()
            .get()
        )
    except Exception:
        return None


def resolve_observer_job_id(workspace: WorkspaceClient) -> int:
    """Resolve o job do Observer via widget, env var ou busca por nome."""
    configured = OBSERVER_JOB_ID or os.environ.get("OBSERVER_JOB_ID", "").strip()
    if configured:
        return int(configured)

    jobs = list(workspace.jobs.list(name=OBSERVER_JOB_NAME))
    if not jobs:
        raise ValueError(
            "Observer job nao encontrado. Defina observer_job_id/OBSERVER_JOB_ID "
            "ou crie o workflow_observer_agent antes de usar o sentinel."
        )

    return int(jobs[0].job_id)


# COMMAND ----------

# DBTITLE 1,Resolver Run Atual e Falhas do Workflow
tags = collect_context_tags()
runtime = resolve_runtime_context(tags, current_run_id=resolve_current_run_id())

w = WorkspaceClient()
parent_run = w.jobs.get_run(run_id=runtime.parent_run_id)
failed_tasks = extract_failed_task_keys(parent_run.tasks or [])
job_name = tags.get("jobName") or parent_run.run_name or "unknown"

logger.info(f"Parent run: {runtime.parent_run_id}")
logger.info(f"Job name: {job_name}")
logger.info(f"Failed tasks: {failed_tasks}")

if not failed_tasks:
    try:
        dbutils.jobs.taskValues.set(key="status", value="SKIP")
    except Exception:
        pass
    dbutils.notebook.exit("SKIP: nenhuma falha real detectada para acionar o Observer")

# COMMAND ----------

# DBTITLE 1,Disparar Job do Observer
observer_job_id = resolve_observer_job_id(w)
notebook_params = build_observer_notebook_params(
    catalog=CATALOG,
    scope=SCOPE,
    source_run_id=runtime.parent_run_id,
    source_job_id=runtime.job_id,
    source_job_name=job_name,
    failed_tasks=failed_tasks,
    llm_provider=LLM_PROVIDER,
    git_provider=GIT_PROVIDER,
)

observer_run = w.jobs.run_now(
    job_id=observer_job_id,
    notebook_params=notebook_params,
)

try:
    dbutils.jobs.taskValues.set(key="status", value="SUCCESS")
    dbutils.jobs.taskValues.set(key="observer_run_id", value=str(observer_run.run_id))
    dbutils.jobs.taskValues.set(key="failed_tasks", value=",".join(failed_tasks))
except Exception:
    pass

dbutils.notebook.exit(
    "SUCCESS: observer disparado "
    f"(observer_job_id={observer_job_id}, observer_run_id={observer_run.run_id}, "
    f"source_run_id={runtime.parent_run_id}, failed_tasks={failed_tasks})"
)
