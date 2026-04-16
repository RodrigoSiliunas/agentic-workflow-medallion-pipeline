# Databricks notebook source
# MAGIC %md
# MAGIC # Gold: Analytics Orchestrator
# MAGIC Executa todos os notebooks Gold na ordem correta de dependencias.
# MAGIC Cada notebook e executado via `dbutils.notebook.run()` com timeout de 10 min.
# MAGIC
# MAGIC **Camada:** Gold (orquestrador) | **Dependencia:** todas as tabelas Silver
# MAGIC **Output:** todas as tabelas Gold (funil, agent_performance, sentiment, etc.)
# MAGIC
# MAGIC _Ultima atualizacao: 2026-04-09_

# COMMAND ----------

# DBTITLE 1,Imports e Setup
import logging
import sys
import time

import yaml

# Auto-detect repo path para pipeline_lib
_nb_path = dbutils.notebook.entry_point.getDbutils().notebook().getContext().notebookPath().get()
_repo_root = "/".join(_nb_path.split("/")[:4])
PIPELINE_ROOT = f"/Workspace{_repo_root}/pipelines/pipeline-seguradora-whatsapp"
sys.path.insert(0, PIPELINE_ROOT)

from pipeline_lib.orchestration import PhasedNotebookRunner

logger = logging.getLogger("gold.analytics")
start_time = time.time()

# COMMAND ----------

# DBTITLE 1,Parametros
dbutils.widgets.text("catalog", "medallion", "Catalog Name")
dbutils.widgets.text("scope", "medallion-pipeline", "Secret Scope")

CATALOG = dbutils.widgets.get("catalog")
SCOPE = dbutils.widgets.get("scope")

# COMMAND ----------

# DBTITLE 1,Executar Notebooks via PhasedNotebookRunner
# Config YAML em config/gold_phases.yaml — adicionar novo notebook =
# 1 linha no YAML; sem edit neste notebook.
CONFIG_PATH = f"{PIPELINE_ROOT}/config/gold_phases.yaml"
TIMEOUT = 600  # 10 min por notebook
NOTEBOOK_BASE = f"{_repo_root}/pipelines/pipeline-seguradora-whatsapp/notebooks"

# O YAML armazena caminhos relativos a `notebooks/`. Expandimos em runtime
# pro caminho absoluto do Repo Databricks.
with open(CONFIG_PATH) as _handle:
    _cfg = yaml.safe_load(_handle)
for _phase in _cfg.get("phases", []):
    for _nb in _phase.get("notebooks", []):
        _nb["path"] = f"{NOTEBOOK_BASE}/{_nb['path']}"

runner = PhasedNotebookRunner.from_dict(_cfg)
phase_results = runner.run(dbutils, timeout=TIMEOUT)

# Agrega resultados + erros no formato legacy pra manter compat com o
# bloco de resumo abaixo.
results: dict[str, str] = {}
errors: list[str] = []
for phase_result in phase_results:
    results.update(phase_result.results)
    errors.extend(phase_result.errors)

# COMMAND ----------

# DBTITLE 1,Resumo da Execucao
# Calcula estatisticas de sucesso/falha
total = len(results)
succeeded = sum(1 for v in results.values() if str(v).startswith("SUCCESS"))
failed = total - succeeded

duration = round(time.time() - start_time, 2)

summary = f"{succeeded}/{total} notebooks OK, {failed} falhas, {duration}s"
logger.info(summary)

# Seta task values (disponiveis para o Observer em caso de falha)
try:
    dbutils.jobs.taskValues.set(key="status", value="SUCCESS" if failed == 0 else "PARTIAL")
    dbutils.jobs.taskValues.set(key="succeeded", value=succeeded)
    dbutils.jobs.taskValues.set(key="failed", value=failed)
    dbutils.jobs.taskValues.set(key="duration_sec", value=duration)
    dbutils.jobs.taskValues.set(key="errors", value=str(errors) if errors else "none")
except Exception:
    pass

if failed > 0:
    dbutils.notebook.exit(f"PARTIAL: {summary}\nErrors: {errors}")
else:
    dbutils.notebook.exit(f"SUCCESS: {summary}")
