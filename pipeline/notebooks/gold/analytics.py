# Databricks notebook source
# MAGIC %md
# MAGIC # Gold: Analytics Orchestrator
# MAGIC Executa todos os notebooks Gold na ordem correta de dependencias.

# COMMAND ----------

dbutils.widgets.text("catalog", "medallion", "Catalog Name")
dbutils.widgets.text("scope", "medallion-pipeline", "Secret Scope")

CATALOG = dbutils.widgets.get("catalog")
SCOPE = dbutils.widgets.get("scope")

# COMMAND ----------

import logging
import time

logger = logging.getLogger("gold.analytics")
start_time = time.time()

# COMMAND ----------

try:
    should_process = dbutils.jobs.taskValues.get(
        taskKey="agent_pre", key="should_process", default=True
    )
    if not should_process:
        dbutils.notebook.exit("SKIP")
except Exception:
    pass

# COMMAND ----------

# MAGIC %md
# MAGIC ## Executar Notebooks na Ordem de Dependencias

# COMMAND ----------

# Auto-detect repo path for sub-notebook calls
_nb_path = dbutils.notebook.entry_point.getDbutils().notebook().getContext().notebookPath().get()
_repo_root = "/".join(_nb_path.split("/")[:5])
NOTEBOOK_BASE = f"{_repo_root}/pipeline/notebooks"

TIMEOUT = 600  # 10 min por notebook

notebooks = [
    # Phase 1: Core (sentimento primeiro, lead_scoring depende dele)
    ("funnel", f"{NOTEBOOK_BASE}/gold/funnel"),
    ("agent_performance", f"{NOTEBOOK_BASE}/gold/agent_performance"),
    ("sentiment", f"{NOTEBOOK_BASE}/gold/sentiment"),
    ("email_providers", f"{NOTEBOOK_BASE}/gold/email_providers"),
    ("lead_scoring", f"{NOTEBOOK_BASE}/gold/lead_scoring"),
    # Phase 2: Analytics (campaign_roi depende de lead_scoring)
    ("temporal_analysis", f"{NOTEBOOK_BASE}/gold/temporal_analysis"),
    ("competitor_intel", f"{NOTEBOOK_BASE}/gold/competitor_intel"),
    ("campaign_roi", f"{NOTEBOOK_BASE}/gold/campaign_roi"),
    # Phase 3: Diferenciais (segmentation depende de sentiment + lead_scoring)
    ("segmentation", f"{NOTEBOOK_BASE}/gold/segmentation"),
    ("churn_reengagement", f"{NOTEBOOK_BASE}/gold/churn_reengagement"),
    ("negotiation_complexity", f"{NOTEBOOK_BASE}/gold/negotiation_complexity"),
    ("first_contact_resolution", f"{NOTEBOOK_BASE}/gold/first_contact_resolution"),
]

results = {}
errors = []

for name, path in notebooks:
    try:
        logger.info(f"Executando: {name}")
        result = dbutils.notebook.run(path, TIMEOUT)
        results[name] = result
        logger.info(f"  OK: {result}")
    except Exception as e:
        error_msg = f"{name} falhou: {e}"
        logger.error(error_msg)
        errors.append(error_msg)
        results[name] = f"FAILED: {e}"

# COMMAND ----------

# MAGIC %md
# MAGIC ## Resumo

# COMMAND ----------

total = len(notebooks)
succeeded = sum(1 for v in results.values() if v.startswith("SUCCESS"))
failed = total - succeeded

duration = round(time.time() - start_time, 2)

summary = f"{succeeded}/{total} notebooks OK, {failed} falhas, {duration}s"
logger.info(summary)

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
