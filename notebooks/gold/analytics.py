# Databricks notebook source
# MAGIC %md
# MAGIC # Gold: Analytics Orchestrator
# MAGIC Executa todos os notebooks Gold na ordem correta de dependencias.

import logging
import time

logger = logging.getLogger("gold.analytics")
start_time = time.time()

# ============================================================
# TASK VALUES
# ============================================================
try:
    should_process = dbutils.jobs.taskValues.get(
        taskKey="agent_pre", key="should_process", default=True
    )
    if not should_process:
        dbutils.notebook.exit("SKIP")
except Exception:
    pass

# ============================================================
# EXECUTAR NOTEBOOKS NA ORDEM DE DEPENDENCIAS
# ============================================================
TIMEOUT = 600  # 10 min por notebook

notebooks = [
    # Phase 1: Core (sentimento primeiro, lead_scoring depende dele)
    ("funnel", "/notebooks/gold/funnel"),
    ("agent_performance", "/notebooks/gold/agent_performance"),
    ("sentiment", "/notebooks/gold/sentiment"),
    ("email_providers", "/notebooks/gold/email_providers"),
    ("lead_scoring", "/notebooks/gold/lead_scoring"),  # depende de sentiment
    # Phase 2: Analytics (campaign_roi depende de lead_scoring)
    ("temporal_analysis", "/notebooks/gold/temporal_analysis"),
    ("competitor_intel", "/notebooks/gold/competitor_intel"),
    ("campaign_roi", "/notebooks/gold/campaign_roi"),  # depende de lead_scoring
    # Phase 3: Diferenciais (segmentation depende de sentiment + lead_scoring)
    ("segmentation", "/notebooks/gold/segmentation"),  # depende de sentiment + lead_scoring
    ("churn_reengagement", "/notebooks/gold/churn_reengagement"),
    ("negotiation_complexity", "/notebooks/gold/negotiation_complexity"),
    ("first_contact_resolution", "/notebooks/gold/first_contact_resolution"),
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

# ============================================================
# RESUMO
# ============================================================
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
