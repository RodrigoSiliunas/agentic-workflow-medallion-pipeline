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
dbutils.widgets.text("llm_provider", "anthropic", "LLM Provider (anthropic|openai|ollama)")
dbutils.widgets.text("git_provider", "github", "Git Provider (github)")

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
    # Usa o metodo do observer para evitar duplicacao de logica
    failure = observer.build_failure_from_run(
        run_id=int(SOURCE_RUN_ID),
        job_id=int(SOURCE_JOB_ID) if SOURCE_JOB_ID else 0,
    )
    failures = [failure]
    log.append(f"Tasks com falha: {failure['failed_tasks']}")
else:
    log.append("Modo: busca automatica (ultimas 2h)")
    failures = observer.find_recent_failures(hours=2)
    log.append(f"Falhas encontradas: {len(failures)}")

if not failures or not failures[0].get("failed_tasks"):
    log_str = " | ".join(log)
    dbutils.notebook.exit(f"OK: nenhuma falha para diagnosticar || LOG: {log_str}")

# COMMAND ----------

# DBTITLE 1,Inicializar Providers via Factory
from pipeline_lib.agent.observer.providers import (
    DiagnosisRequest,
    create_llm_provider,
    create_git_provider,
)

LLM_PROVIDER = dbutils.widgets.get("llm_provider")
GIT_PROVIDER = dbutils.widgets.get("git_provider")

# Cria providers via factory — qualquer combinacao funciona
llm = create_llm_provider(
    LLM_PROVIDER,
    api_key=os.environ.get("ANTHROPIC_API_KEY", ""),
    model=os.environ.get("LLM_MODEL", "claude-opus-4-20250514"),
)
git = create_git_provider(
    GIT_PROVIDER,
    token=os.environ.get("GITHUB_TOKEN", ""),
    repo=os.environ.get("GITHUB_REPO", ""),
)

log.append(f"LLM provider: {llm.name}")
log.append(f"Git provider: {git.name}")

# COMMAND ----------

# DBTITLE 1,Coletar Contexto e Diagnosticar
results = []

for failure in failures:
    log.append(f"--- Processando: {failure['job_name']} ---")

    # Coletar contexto completo via Workspace API
    ctx = observer.build_context(failure)
    log.append(f"Codigo: {len(ctx['notebook_code'])} chars")
    log.append(f"Erro: {ctx['error_message'][:150]}")

    # Diagnostico via LLM provider (factory pattern)
    log.append(f"Chamando {llm.name}...")
    try:
        request = DiagnosisRequest(
            error_message=ctx["error_message"],
            stack_trace=ctx["error_message"],
            failed_task=ctx["failed_task"],
            notebook_code=ctx["notebook_code"],
            schema_info=ctx["schema_info"],
            pipeline_state=ctx["pipeline_state"],
        )
        diagnosis = llm.diagnose(request)

        log.append(f"Provider: {diagnosis.provider}/{diagnosis.model}")
        log.append(f"Tokens: in={diagnosis.input_tokens}, out={diagnosis.output_tokens}")
        log.append(f"Diagnostico: {diagnosis.diagnosis[:200]}")
        log.append(f"Confianca: {diagnosis.confidence:.0%}")

        # Criar PR via Git provider (factory pattern)
        if diagnosis.fixed_code and diagnosis.file_to_fix:
            log.append(f"Criando PR para {diagnosis.file_to_fix}...")
            try:
                pr = git.create_fix_pr(diagnosis, ctx["failed_task"])
                log.append(f"PR #{pr.pr_number}: {pr.pr_url}")
                results.append({
                    "job": failure["job_name"],
                    "task": ctx["failed_task"],
                    "pr": pr.pr_url,
                    "confidence": diagnosis.confidence,
                })
            except Exception as e:
                log.append(f"ERRO PR: {e}")
        else:
            log.append("LLM nao gerou fix")

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
