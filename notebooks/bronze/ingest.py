# Databricks notebook source
# MAGIC %md
# MAGIC # Bronze Ingestion
# MAGIC Le Parquet cru do S3 `/bronze/`, valida schema, e salva como Delta Table `bronze.conversations`.

import hashlib
import logging
import time

logger = logging.getLogger("bronze.ingest")

# ============================================================
# CONFIGURACAO
# ============================================================
BRONZE_S3_PATH = spark.conf.get("pipeline.bronze_s3_path", "s3://medallion-pipeline/bronze/")
CATALOG = spark.conf.get("pipeline.catalog", "medallion")
BRONZE_TABLE = f"{CATALOG}.bronze.conversations"

# ============================================================
# 1. VERIFICAR TASK VALUES DO AGENTE (se rodando via Workflow)
# ============================================================
try:
    should_process = dbutils.jobs.taskValues.get(
        taskKey="agent_pre", key="should_process", default=True
    )
    if not should_process:
        dbutils.notebook.exit("SKIP: agent decided no processing needed")
    bronze_path = dbutils.jobs.taskValues.get(
        taskKey="agent_pre", key="bronze_path", default=BRONZE_S3_PATH
    )
except Exception:
    # Execucao standalone (sem Workflow) — usar config default
    bronze_path = BRONZE_S3_PATH
    logger.info("Executando standalone (sem agent_pre)")

# ============================================================
# 2. LER PARQUET DO S3
# ============================================================
start_time = time.time()
logger.info(f"Lendo Parquet de: {bronze_path}")

df = spark.read.parquet(bronze_path)
row_count = df.count()
columns = set(df.columns)

logger.info(f"Linhas lidas: {row_count}")
logger.info(f"Colunas encontradas: {sorted(columns)}")

# ============================================================
# 3. VALIDAR SCHEMA COM EVOLUTION
# ============================================================
# Importar lib de validacao (deployada via Databricks Repos ou wheel)
import sys
sys.path.insert(0, "/Workspace/Repos/pipeline_lib")  # Ajustar path conforme deploy

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

# ============================================================
# 4. SALVAR COMO DELTA TABLE (com schema evolution)
# ============================================================
logger.info(f"Salvando como Delta Table: {BRONZE_TABLE}")

(
    df.write
    .format("delta")
    .mode("overwrite")
    .option("mergeSchema", "true")
    .saveAsTable(BRONZE_TABLE)
)

# Verificar resultado
saved_count = spark.table(BRONZE_TABLE).count()
logger.info(f"Delta Table salva: {saved_count} linhas")

# ============================================================
# 5. FINGERPRINT VIA S3 METADATA
# ============================================================
def get_s3_fingerprint(path: str) -> str:
    """Gera fingerprint dos arquivos no S3 via metadata."""
    files = dbutils.fs.ls(path)
    fingerprint = "|".join(
        f"{f.name}:{f.size}:{f.modificationTime}"
        for f in sorted(files, key=lambda x: x.name)
    )
    return hashlib.sha256(fingerprint.encode()).hexdigest()

try:
    fingerprint = get_s3_fingerprint(bronze_path)
    logger.info(f"Fingerprint S3: {fingerprint[:16]}...")
except Exception as e:
    fingerprint = f"unknown_{row_count}"
    logger.warning(f"Nao foi possivel calcular fingerprint: {e}")

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
