# Databricks notebook source
# MAGIC %md
# MAGIC # Bronze Ingestion
# MAGIC Le Parquet cru do S3 `/bronze/`, valida schema, e salva como Delta Table `bronze.conversations`.

# COMMAND ----------

import hashlib
import logging
import sys
import time

logger = logging.getLogger("bronze.ingest")

# COMMAND ----------

# ============================================================
# IMPORTAR S3Lake (boto3 + Databricks Secrets)
# ============================================================
sys.path.insert(0, "/Workspace/Repos/rodrigosiliunas1@gmail.com/agentic-workflow-medallion-pipeline/pipeline")
from pipeline_lib.storage import S3Lake

lake = S3Lake(dbutils, spark)

# COMMAND ----------

# ============================================================
# CONFIGURACAO
# ============================================================
BRONZE_S3_PREFIX = "bronze/"
CATALOG = "medallion"
BRONZE_TABLE = f"{CATALOG}.bronze.conversations"

# COMMAND ----------

# ============================================================
# 1. VERIFICAR TASK VALUES DO AGENTE (se rodando via Workflow)
# ============================================================
try:
    should_process = dbutils.jobs.taskValues.get(
        taskKey="agent_pre", key="should_process", default=True
    )
    if not should_process:
        dbutils.notebook.exit("SKIP: agent decided no processing needed")
    bronze_prefix = dbutils.jobs.taskValues.get(
        taskKey="agent_pre", key="bronze_prefix", default=BRONZE_S3_PREFIX
    )
except Exception:
    # Execucao standalone (sem Workflow) — usar config default
    bronze_prefix = BRONZE_S3_PREFIX
    logger.info("Executando standalone (sem agent_pre)")

# COMMAND ----------

# ============================================================
# 2. LER PARQUET DO S3 (via boto3 in-memory → Spark DataFrame)
# ============================================================
start_time = time.time()

df = lake.read_parquet(bronze_prefix)
row_count = int(df.count())
columns = set(df.columns)

logger.info(f"Linhas lidas: {row_count}")
logger.info(f"Colunas encontradas: {sorted(columns)}")

# COMMAND ----------

# ============================================================
# 3. VALIDAR SCHEMA COM EVOLUTION
# ============================================================
# Importar lib de validacao (ja no sys.path via S3Lake import acima)
from pipeline_lib.schema.contracts import REQUIRED_COLUMNS
from pipeline_lib.schema.validator import validate_schema

validation = validate_schema(columns)

if not validation.is_valid:
    error_msg = f"Schema invalido: {validation.errors}"
    logger.error(error_msg)
    try:
        dbutils.jobs.taskValues.set(key="status", value="FAILED")
        dbutils.jobs.taskValues.set(key="error", value=error_msg)
    except Exception:
        pass
    raise ValueError(error_msg)

if validation.warnings:
    for warning in validation.warnings:
        logger.warning(warning)

# COMMAND ----------

# ============================================================
# 4. SALVAR COMO DELTA TABLE (com schema evolution) + S3
# ============================================================
logger.info(f"Salvando como Delta Table: {BRONZE_TABLE}")

# 4a. Salvar no Unity Catalog (para queries SQL no Databricks)
(
    df.write
    .format("delta")
    .mode("overwrite")
    .option("mergeSchema", "true")
    .saveAsTable(BRONZE_TABLE)
)

# Verificar resultado
saved_count = int(spark.table(BRONZE_TABLE).count())
logger.info(f"Delta Table salva (UC): {saved_count} linhas")

# 4b. Upload para S3 (data lake persistente, in-memory)
# Lemos da tabela UC (DF limpo, sem plan metrics do Spark)
lake.write_parquet(spark.table(BRONZE_TABLE), "bronze/conversations/")
logger.info("Parquet uploaded para S3 bronze/conversations/")

# COMMAND ----------

# ============================================================
# 5. FINGERPRINT VIA S3 METADATA
# ============================================================
def get_s3_fingerprint(prefix: str) -> str:
    """Gera fingerprint dos arquivos no S3 via metadata (boto3)."""
    items = lake.get_metadata(prefix)
    fingerprint = "|".join(
        f"{item['key']}:{item['size']}:{item['last_modified']}"
        for item in sorted(items, key=lambda x: x["key"])
    )
    return hashlib.sha256(fingerprint.encode()).hexdigest()

try:
    fingerprint = get_s3_fingerprint(bronze_prefix)
    logger.info(f"Fingerprint S3: {fingerprint[:16]}...")
except Exception as e:
    fingerprint = f"unknown_{row_count}"
    logger.warning(f"Nao foi possivel calcular fingerprint: {e}")

# COMMAND ----------

# ============================================================
# 6. METRICAS E TASK VALUES
# ============================================================
duration_sec = round(time.time() - start_time, 2)

metrics = {
    "rows_input": row_count,
    "rows_output": saved_count,
    "columns_count": len(columns),
    "new_columns": len(columns - REQUIRED_COLUMNS),
    "duration_sec": duration_sec,
    "fingerprint": fingerprint,
}

logger.info(f"Bronze ingestion completa em {duration_sec}s: {metrics}")

try:
    dbutils.jobs.taskValues.set(key="status", value="SUCCESS")
    dbutils.jobs.taskValues.set(key="rows_output", value=saved_count)
    dbutils.jobs.taskValues.set(key="duration_sec", value=duration_sec)
    dbutils.jobs.taskValues.set(key="fingerprint", value=fingerprint)
    dbutils.jobs.taskValues.set(
        key="schema_warnings",
        value=str(validation.warnings) if validation.warnings else "none",
    )
except Exception:
    pass  # Execucao standalone

dbutils.notebook.exit(f"SUCCESS: {saved_count} rows ingested in {duration_sec}s")
