# Databricks notebook source
# MAGIC %md
# MAGIC # Workflow Observer — Agente AI Autonomo
# MAGIC Recebe o run_id de um workflow que falhou, coleta contexto completo
# MAGIC (codigo fonte via Workspace API + logs + schema), chama Claude Opus
# MAGIC para diagnostico e cria PR no GitHub.
# MAGIC
# MAGIC **Tipo:** Observer (independente) | **Trigger:** Sob demanda (via SDK)
# MAGIC **Generico** — funciona com qualquer workflow do workspace.
# MAGIC
# MAGIC _Ultima atualizacao: 2026-04-09_

# COMMAND ----------

# DBTITLE 1,Imports e Setup
from datetime import datetime

import json
import logging
import os
import sys
import time

# Auto-detect repo path
_nb_path = dbutils.notebook.entry_point.getDbutils().notebook().getContext().notebookPath().get()
_repo_root = "/".join(_nb_path.split("/")[:4])
PIPELINE_ROOT = f"/Workspace{_repo_root}/pipeline"
sys.path.insert(0, PIPELINE_ROOT)

from databricks.sdk import WorkspaceClient
from pipeline_lib.agent.observer import WorkflowObserver

logger = logging.getLogger("observer")

# COMMAND ----------

# DBTITLE 1,Parametros
# source_run_id: run que falhou (passado pelo pipeline via SDK)
# Se vazio, busca falhas recentes (fallback para execucao manual)
dbutils.widgets.text("scope", "medallion-pipeline", "Secret Scope")
dbutils.widgets.text("source_run_id", "", "Run ID que falhou")
dbutils.widgets.text("source_job_id", "", "Job ID que falhou")

SCOPE = dbutils.widgets.get("scope")
SOURCE_RUN_ID = dbutils.widgets.get("source_run_id")
SOURCE_JOB_ID = dbutils.widgets.get("source_job_id")

# Credenciais do agente AI
os.environ["ANTHROPIC_API_KEY"] = dbutils.secrets.get(SCOPE, "anthropic-api-key")
os.environ["GITHUB_TOKEN"] = dbutils.secrets.get(SCOPE, "github-token")
os.environ["GITHUB_REPO"] = dbutils.secrets.get(SCOPE, "github-repo")

# COMMAND ----------

# MAGIC %pip install anthropic PyGithub --quiet

# COMMAND ----------

# DBTITLE 1,Inicializar Observer
w = WorkspaceClient()
observer = WorkflowObserver(w)
log = []

log.append(f"Observer iniciado: {datetime.now().isoformat()}")

# COMMAND ----------

# DBTITLE 1,Identificar Falhas
# Modo 1: run_id especifico (triggered pelo pipeline)
# Modo 2: busca falhas recentes (execucao manual/debug)
if SOURCE_RUN_ID:
    log.append(f"Modo: triggered (run_id={SOURCE_RUN_ID})")
    run = w.jobs.get_run(run_id=int(SOURCE_RUN_ID))
    job_name = run.run_name or "unknown"

    # Coletar tasks que falharam
    failed_tasks = []
    errors = {}
    for task in run.tasks:
        result = str(task.state.result_state) if task.state else ""
        if "FAILED" in result:
            try:
                out = w.jobs.get_run_output(run_id=task.run_id)
                error = out.error or "Unknown"
            except Exception:
                error = "Could not retrieve"
            failed_tasks.append(task.task_key)
            errors[task.task_key] = error[:500]

    failures = [{
        "job_id": int(SOURCE_JOB_ID) if SOURCE_JOB_ID else 0,
        "job_name": job_name,
        "run_id": int(SOURCE_RUN_ID),
        "failed_tasks": failed_tasks,
        "errors": errors,
        "timestamp": str(run.start_time),
    }]
    log.append(f"Tasks com falha: {failed_tasks}")
else:
    log.append("Modo: busca automatica (ultimas 2h)")
    failures = observer.find_recent_failures(hours=2)
    log.append(f"Falhas encontradas: {len(failures)}")

if not failures or not failures[0].get("failed_tasks"):
    log_str = " | ".join(log)
    dbutils.notebook.exit(f"OK: nenhuma falha para diagnosticar || LOG: {log_str}")

# COMMAND ----------

# DBTITLE 1,Coletar Contexto e Diagnosticar
from pipeline_lib.agent.llm_diagnostics import diagnose_error
from pipeline_lib.agent.github_pr import create_fix_pr

results = []

for failure in failures:
    log.append(f"--- Processando: {failure['job_name']} ---")

    # Coletar contexto completo via Workspace API
    ctx = observer.build_context(failure)
    code_len = len(ctx["notebook_code"])
    log.append(f"Codigo: {code_len} chars")
    log.append(f"Erro: {ctx['error_message'][:150]}")

    # Claude Opus
    log.append("Chamando Claude Opus 4.6...")
    try:
        diagnosis = diagnose_error(
            error_message=ctx["error_message"],
            stack_trace=ctx["error_message"],
            failed_task=ctx["failed_task"],
            notebook_code=ctx["notebook_code"],
            schema_info=ctx["schema_info"],
            pipeline_state=ctx["pipeline_state"],
        )

        model = diagnosis.get("_model", "unknown")
        in_tok = diagnosis.get("_input_tokens", 0)
        out_tok = diagnosis.get("_output_tokens", 0)
        conf = diagnosis.get("confidence", 0)

        log.append(f"Modelo: {model} (in={in_tok}, out={out_tok})")
        log.append(f"Diagnostico: {diagnosis.get('diagnosis', 'N/A')[:200]}")
        log.append(f"Confianca: {conf:.0%}")

        # Criar PR se tem fix
        if diagnosis.get("fixed_code") and diagnosis.get("file_to_fix"):
            log.append(f"Criando PR para {diagnosis['file_to_fix']}...")
            try:
                pr = create_fix_pr(
                    fix_description=diagnosis.get("fix_description", ""),
                    diagnosis=diagnosis.get("diagnosis", ""),
                    file_path=diagnosis["file_to_fix"],
                    fixed_code=diagnosis["fixed_code"],
                    failed_task=ctx["failed_task"],
                    confidence=conf,
                )
                log.append(f"PR #{pr['pr_number']}: {pr['pr_url']}")
                results.append({
                    "job": failure["job_name"],
                    "task": ctx["failed_task"],
                    "pr": pr["pr_url"],
                    "confidence": conf,
                })
            except Exception as e:
                log.append(f"ERRO PR: {e}")
        else:
            log.append("LLM nao gerou fix — intervencao manual")

    except Exception as e:
        log.append(f"ERRO AI: {e}")

# COMMAND ----------

# DBTITLE 1,Resultado
summary = (
    f"Processado: {len(failures)} falhas, "
    f"{len(results)} PRs criados"
)
log.append(summary)

log_str = " | ".join(log)
dbutils.notebook.exit(f"{summary} || LOG: {log_str}")
