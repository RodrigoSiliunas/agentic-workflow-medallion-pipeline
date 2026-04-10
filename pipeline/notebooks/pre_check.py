# Databricks notebook source
# MAGIC %md
# MAGIC # Pre-Check (Task 0)
# MAGIC Pre-flight check do pipeline ETL: le parametros, propaga chaos_mode para
# MAGIC as tasks downstream e gera um run_id unico para rastreamento.
# MAGIC
# MAGIC **Pipeline eh ETL puro** (overwrite idempotente). Nao captura versoes
# MAGIC Delta nem faz rollback — em caso de falha, o workflow_observer_agent eh
# MAGIC disparado automaticamente pelo task sentinel `observer_trigger`.
# MAGIC
# MAGIC **Camada:** Orquestrador | **Output:** task values (run_id, chaos_mode, bronze_prefix)
# MAGIC
# MAGIC _Ultima atualizacao: 2026-04-09_

# COMMAND ----------

# DBTITLE 1,Imports e Setup
import logging
from datetime import datetime

logger = logging.getLogger("pre_check")

# COMMAND ----------

# DBTITLE 1,Parametros
# Widgets permitem parametrizar o notebook ao ser chamado pelo workflow
dbutils.widgets.text("catalog", "medallion", "Catalog Name")
dbutils.widgets.text("scope", "medallion-pipeline", "Secret Scope")
dbutils.widgets.text("bronze_prefix", "bronze/", "Bronze S3 Prefix")
dbutils.widgets.text(
    "chaos_mode",
    "off",
    "Chaos Mode (off|bronze_schema|silver_null|gold_divide_zero|validation_strict)",
)

CATALOG = dbutils.widgets.get("catalog")
SCOPE = dbutils.widgets.get("scope")
BRONZE_PREFIX = dbutils.widgets.get("bronze_prefix")
CHAOS_MODE = dbutils.widgets.get("chaos_mode")

# COMMAND ----------

# DBTITLE 1,Gerar Run ID e Propagar Task Values
# run_id unico baseado no timestamp (util para logs e rastreamento cross-task)
run_id = datetime.now().strftime("%Y%m%d_%H%M%S")

# Task values sao lidos pelas tasks seguintes do workflow via dbutils.jobs.taskValues
dbutils.jobs.taskValues.set(key="run_id", value=run_id)
dbutils.jobs.taskValues.set(key="bronze_prefix", value=BRONZE_PREFIX)
dbutils.jobs.taskValues.set(key="chaos_mode", value=CHAOS_MODE)

# COMMAND ----------

# DBTITLE 1,Alerta de Chaos Mode
# Aviso visual no output do notebook quando chaos mode esta ativo
if CHAOS_MODE != "off":
    print("\n" + "!" * 60)
    print(f"  CHAOS MODE ATIVADO: {CHAOS_MODE}")
    print("  Uma falha controlada sera injetada neste pipeline run.")
    print("!" * 60 + "\n")
    logger.warning(f"CHAOS MODE ativo: {CHAOS_MODE}")

logger.info(f"Pre-check OK. run_id={run_id}, chaos_mode={CHAOS_MODE}")
dbutils.notebook.exit(f"OK: run_id={run_id}, chaos={CHAOS_MODE}")
