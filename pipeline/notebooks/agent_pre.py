# Databricks notebook source
# MAGIC %md
# MAGIC # Agent Pre-Check (Task 0)
# MAGIC Verifica dados novos, captura versoes Delta para rollback, seta task values.

import hashlib
import json
import logging
import time
from datetime import datetime

logger = logging.getLogger("agent_pre")

# ============================================================
# CONFIGURACAO
# ============================================================
CATALOG = spark.conf.get("pipeline.catalog", "medallion")
BRONZE_PATH = spark.conf.get("pipeline.bronze_path", "s3://namastex-medallion-datalake/bronze/")
STATE_TABLE = f"{CATALOG}.pipeline.state"

# ============================================================
# 1. CRIAR TABELA DE ESTADO (se nao existir)
# ============================================================
spark.sql(f"""
    CREATE TABLE IF NOT EXISTS {STATE_TABLE} (
        run_at                STRING,
        last_bronze_hash      STRING,
        status                STRING,
        consecutive_failures  INT,
        delta_versions        STRING
    )
    USING DELTA
""")

# ============================================================
# 2. CARREGAR ESTADO ANTERIOR
# ============================================================
def load_state() -> dict:
    """Carrega o estado da ultima execucao."""
    if spark.catalog.tableExists(STATE_TABLE):
        row = spark.table(STATE_TABLE).orderBy(
            spark.table(STATE_TABLE)["run_at"].desc()
        ).first()
        if row:
            return row.asDict()
    return {
        "last_bronze_hash": None,
        "last_run_at": None,
        "consecutive_failures": 0,
    }

state = load_state()
logger.info(f"Estado anterior: status={state.get('status')}, "
            f"failures={state.get('consecutive_failures')}")

# ============================================================
# 3. VERIFICAR DADOS NOVOS (fingerprint via metadata)
# ============================================================
def get_bronze_fingerprint(path: str) -> str:
    """Gera fingerprint dos dados Bronze via metadata do filesystem."""
    try:
        files = dbutils.fs.ls(path)
        fingerprint = "|".join(
            f"{f.name}:{f.size}:{f.modificationTime}"
            for f in sorted(files, key=lambda x: x.name)
        )
        return hashlib.sha256(fingerprint.encode()).hexdigest()
    except Exception as e:
        logger.warning(f"Nao conseguiu ler {path}: {e}")
        return f"error_{int(time.time())}"

current_hash = get_bronze_fingerprint(BRONZE_PATH)
has_new_data = current_hash != state.get("last_bronze_hash")

if not has_new_data:
    logger.info("Sem dados novos. Encerrando.")
    dbutils.jobs.taskValues.set(key="should_process", value=False)
    dbutils.notebook.exit("SKIP: no new data")

logger.info(f"Dados novos detectados! Hash: {current_hash[:16]}...")

# ============================================================
# 4. CAPTURAR VERSOES DELTA (para rollback no agent_post)
# ============================================================
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
    """Captura a versao atual de cada Delta Table para rollback."""
    versions = {}
    for table in tables:
        try:
            if spark.catalog.tableExists(table):
                history = spark.sql(f"DESCRIBE HISTORY {table} LIMIT 1").first()
                versions[table] = history["version"]
        except Exception:
            pass
    return versions

delta_versions = capture_delta_versions(TRACKED_TABLES)
logger.info(f"Versoes Delta capturadas: {len(delta_versions)} tabelas")

# ============================================================
# 5. SETAR TASK VALUES
# ============================================================
run_id = datetime.now().strftime("%Y%m%d_%H%M%S")

dbutils.jobs.taskValues.set(key="should_process", value=True)
dbutils.jobs.taskValues.set(key="bronze_path", value=BRONZE_PATH)
dbutils.jobs.taskValues.set(key="bronze_hash", value=current_hash)
dbutils.jobs.taskValues.set(key="run_id", value=run_id)
dbutils.jobs.taskValues.set(key="delta_versions", value=json.dumps(delta_versions))

logger.info(f"Task values setados. run_id={run_id}")
dbutils.notebook.exit(f"GO: run_id={run_id}, hash={current_hash[:16]}")
