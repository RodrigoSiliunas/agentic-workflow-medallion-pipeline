# Databricks notebook source
# MAGIC %md
# MAGIC # Workflow Observer — Agente AI Autonomo
# MAGIC Monitora workflows do workspace, detecta falhas, coleta contexto completo
# MAGIC (codigo fonte + logs + schema), chama Claude Opus para diagnostico e cria
# MAGIC PR no GitHub com a correcao proposta.
# MAGIC
# MAGIC **Tipo:** Observer (independente) | **Trigger:** Schedule ou manual
# MAGIC **Funciona com qualquer workflow** — nao eh especifico do pipeline Medallion.
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

# COMMAND ----------

# DBTITLE 1,Parametros
dbutils.widgets.text("scope", "medallion-pipeline", "Secret Scope")
dbutils.widgets.text("workflow_name", "", "Workflow Name (vazio = todos)")
dbutils.widgets.text("hours", "1", "Janela de busca (horas)")

SCOPE = dbutils.widgets.get("scope")
WORKFLOW_NAME = dbutils.widgets.get("workflow_name") or None
HOURS = int(dbutils.widgets.get("hours"))

# Credenciais do agente AI
os.environ["ANTHROPIC_API_KEY"] = dbutils.secrets.get(SCOPE, "anthropic-api-key")
os.environ["GITHUB_TOKEN"] = dbutils.secrets.get(SCOPE, "github-token")
os.environ["GITHUB_REPO"] = dbutils.secrets.get(SCOPE, "github-repo")

logger = logging.getLogger("observer")

# COMMAND ----------

# MAGIC %pip install anthropic PyGithub --quiet

# COMMAND ----------

# DBTITLE 1,Inicializar Observer
w = WorkspaceClient()
observer = WorkflowObserver(w)
log = []

log.append(f"Observer iniciado: {datetime.now().isoformat()}")
log.append(f"Workflow filter: {WORKFLOW_NAME or 'todos'}")
log.append(f"Janela: ultimas {HOURS}h")

# COMMAND ----------

# DBTITLE 1,Detectar Falhas Recentes
failures = observer.find_recent_failures(
    hours=HOURS, workflow_name=WORKFLOW_NAME
)

log.append(f"Falhas encontradas: {len(failures)}")

if not failures:
    log_str = " | ".join(log)
    dbutils.notebook.exit(f"OK: nenhuma falha nas ultimas {HOURS}h || LOG: {log_str}")

# Listar falhas encontradas
for f in failures:
    log.append(
        f"  [{f['job_name']}] run={f['run_id']} "
        f"tasks={f['failed_tasks']}"
    )

# COMMAND ----------

# DBTITLE 1,Diagnosticar e Criar PRs
from pipeline_lib.agent.llm_diagnostics import diagnose_error
from pipeline_lib.agent.github_pr import create_fix_pr

results = []

for failure in failures:
    log.append(f"[AI] Processando: {failure['job_name']} run={failure['run_id']}")

    # Coletar contexto completo
    ctx = observer.build_context(failure)
    log.append(f"[AI] Codigo: {len(ctx['notebook_code'])} chars")
    log.append(f"[AI] Schema: coletado")
    log.append(f"[AI] Erro: {ctx['error_message'][:150]}")

    # Chamar Claude Opus
    log.append("[AI] Chamando Claude Opus 4.6...")
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

        log.append(f"[AI] Modelo: {model} (in={in_tok}, out={out_tok})")
        log.append(f"[AI] Diagnostico: {diagnosis.get('diagnosis', 'N/A')[:200]}")
        log.append(f"[AI] Confianca: {conf:.0%}")

        # Criar PR se tem fix
        if diagnosis.get("fixed_code") and diagnosis.get("file_to_fix"):
            log.append(f"[AI] Criando PR para {diagnosis['file_to_fix']}...")
            try:
                pr = create_fix_pr(
                    fix_description=diagnosis.get("fix_description", ""),
                    diagnosis=diagnosis.get("diagnosis", ""),
                    file_path=diagnosis["file_to_fix"],
                    fixed_code=diagnosis["fixed_code"],
                    failed_task=ctx["failed_task"],
                    confidence=conf,
                )
                log.append(f"[AI] PR #{pr['pr_number']}: {pr['pr_url']}")
                results.append({
                    "job": failure["job_name"],
                    "task": ctx["failed_task"],
                    "pr": pr["pr_url"],
                    "confidence": conf,
                })
            except Exception as e:
                log.append(f"[AI] ERRO PR: {e}")
        else:
            log.append("[AI] LLM nao gerou fix — intervencao manual")

    except Exception as e:
        log.append(f"[AI] ERRO: {e}")

# COMMAND ----------

# DBTITLE 1,Resultado
summary = f"Processado: {len(failures)} falhas, {len(results)} PRs criados"
log.append(summary)

log_str = " | ".join(log)
dbutils.notebook.exit(f"{summary} || LOG: {log_str}")
