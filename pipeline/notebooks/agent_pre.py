# Databricks notebook source
# MAGIC %md
# MAGIC # Agent Pre-Check (Task 0)
# MAGIC Verifica se existem dados novos no S3, captura versoes Delta de todas as tabelas
# MAGIC rastreadas para possibilitar rollback, e seta task values para o restante do workflow.
# MAGIC
# MAGIC **Camada:** Orquestrador | **Output:** task values (should_process, bronze_hash, run_id, delta_versions)
# MAGIC
# MAGIC _Ultima atualizacao: 2026-04-09_

# COMMAND ----------

# DBTITLE 1,Imports e Setup
import hashlib
import json
import logging
import os
import sys
import time
from datetime import datetime

# Auto-detect repo path from this notebook's location
_nb_path = dbutils.notebook.entry_point.getDbutils().notebook().getContext().notebookPath().get()
_repo_root = "/".join(_nb_path.split("/")[:5])
PIPELINE_ROOT = f"/Workspace{_repo_root}/pipeline"
sys.path.insert(0, PIPELINE_ROOT)

from pipeline_lib.storage import S3Lake

# COMMAND ----------

# DBTITLE 1,Parametros
# Widgets permitem parametrizar o notebook ao ser chamado pelo workflow
dbutils.widgets.text("catalog", "medallion", "Catalog Name")
dbutils.widgets.text("scope", "medallion-pipeline", "Secret Scope")
dbutils.widgets.text("bronze_prefix", "bronze/", "Bronze S3 Prefix")

CATALOG = dbutils.widgets.get("catalog")
SCOPE = dbutils.widgets.get("scope")
BRONZE_PREFIX = dbutils.widgets.get("bronze_prefix")

# Inicializa o lake client (boto3 wrapper) e o logger
lake = S3Lake(dbutils, spark, scope=SCOPE)
logger = logging.getLogger("agent_pre")

# COMMAND ----------

# DBTITLE 1,Criar Tabela de Estado do Pipeline
# Tabela que persiste o estado entre execucoes (hash anterior, falhas consecutivas, etc.)
STATE_TABLE = f"{CATALOG}.pipeline.state"

spark.sql(f"""
    CREATE TABLE IF NOT EXISTS {STATE_TABLE} (
        run_at                STRING,
        last_bronze_hash      STRING,
        status                STRING,
        consecutive_failures  LONG,
        delta_versions        STRING
    )
    USING DELTA
""")

# COMMAND ----------

# DBTITLE 1,Carregar Estado Anterior
def load_state() -> dict:
    """Carrega o estado da ultima execucao a partir da tabela de estado.
    Retorna dict com campos do ultimo registro ou defaults se vazia."""
    if spark.catalog.tableExists(STATE_TABLE):
        from pyspark.sql import functions as F
        row = spark.table(STATE_TABLE).orderBy(
            F.col("run_at").desc()
        ).first()
        if row:
            return row.asDict()
    # Estado default quando nao existe historico
    return {
        "last_bronze_hash": None,
        "last_run_at": None,
        "consecutive_failures": 0,
    }

state = load_state()
logger.info(f"Estado anterior: status={state.get('status')}, "
            f"failures={state.get('consecutive_failures')}")

# COMMAND ----------

# DBTITLE 1,Verificar Dados Novos
def get_bronze_fingerprint(prefix: str) -> str:
    """Gera fingerprint dos dados Bronze via metadata do S3 (boto3).
    Combina key, size e last_modified de cada arquivo em um hash SHA-256
    para detectar qualquer alteracao nos dados de entrada."""
    try:
        items = lake.get_metadata(prefix)
        # Ordena por key para garantir hash deterministico
        fingerprint = "|".join(
            f"{item['key']}:{item['size']}:{item['last_modified']}"
            for item in sorted(items, key=lambda x: x["key"])
        )
        return hashlib.sha256(fingerprint.encode()).hexdigest()
    except Exception as e:
        logger.warning(f"Nao conseguiu ler S3 prefix {prefix}: {e}")
        # Retorna hash baseado em timestamp para forcar reprocessamento
        return f"error_{int(time.time())}"

# Compara fingerprint atual com o da ultima execucao
current_hash = get_bronze_fingerprint(BRONZE_PREFIX)
has_new_data = current_hash != state.get("last_bronze_hash")

if not has_new_data:
    # Sem alteracoes no S3 - sinaliza para o workflow pular todas as tasks
    logger.info("Sem dados novos. Encerrando.")
    dbutils.jobs.taskValues.set(key="should_process", value=False)
    dbutils.notebook.exit("SKIP: no new data")

logger.info(f"Dados novos detectados! Hash: {current_hash[:16]}...")

# COMMAND ----------

# DBTITLE 1,Capturar Versoes Delta para Rollback
# Lista de todas as tabelas que o pipeline escreve
# Usada para capturar a versao atual de cada tabela antes da execucao,
# permitindo rollback granular em caso de falha
TRACKED_TABLES = [
    f"{CATALOG}.bronze.conversations",
    f"{CATALOG}.silver.messages_clean",
    f"{CATALOG}.silver.leads_profile",
    f"{CATALOG}.silver.conversations_enriched",
    f"{CATALOG}.gold.funil_vendas",
    f"{CATALOG}.gold.agent_performance",
    f"{CATALOG}.gold.sentiment",
    f"{CATALOG}.gold.lead_scoring",
    f"{CATALOG}.gold.email_providers",
    f"{CATALOG}.gold.temporal_analysis",
    f"{CATALOG}.gold.competitor_intel",
    f"{CATALOG}.gold.campaign_roi",
    f"{CATALOG}.gold.personas",
    f"{CATALOG}.gold.churn_reengagement",
    f"{CATALOG}.gold.negotiation_complexity",
    f"{CATALOG}.gold.first_contact_resolution",
]

def capture_delta_versions(tables: list) -> dict:
    """Captura a versao atual de cada Delta Table para rollback.
    Tabelas que nao existem ainda sao ignoradas silenciosamente."""
    versions = {}
    for table in tables:
        try:
            if spark.catalog.tableExists(table):
                history = spark.sql(f"DESCRIBE HISTORY {table} LIMIT 1").first()
                versions[table] = history["version"]
        except Exception:
            # Tabela pode existir mas ter problemas de acesso -- segue em frente
            pass
    return versions

delta_versions = capture_delta_versions(TRACKED_TABLES)
logger.info(f"Versoes Delta capturadas: {len(delta_versions)} tabelas")

# COMMAND ----------

# DBTITLE 1,Setar Task Values para o Workflow
# Gera run_id unico baseado no timestamp da execucao
run_id = datetime.now().strftime("%Y%m%d_%H%M%S")

# Task values sao passados via dbutils para as tasks seguintes do workflow
dbutils.jobs.taskValues.set(key="should_process", value=True)
dbutils.jobs.taskValues.set(key="bronze_prefix", value=BRONZE_PREFIX)
dbutils.jobs.taskValues.set(key="bronze_hash", value=current_hash)
dbutils.jobs.taskValues.set(key="run_id", value=run_id)
dbutils.jobs.taskValues.set(key="delta_versions", value=json.dumps(delta_versions))

logger.info(f"Task values setados. run_id={run_id}")
dbutils.notebook.exit(f"GO: run_id={run_id}, hash={current_hash[:16]}")
