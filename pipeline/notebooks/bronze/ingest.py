# Databricks notebook source
# MAGIC %md
# MAGIC # Bronze Ingestion
# MAGIC Le Parquet cru do S3 `/bronze/`, valida schema contra contracts definidos
# MAGIC em `pipeline_lib.schema`, e salva como Delta Table `bronze.conversations`
# MAGIC no Unity Catalog. Tambem gera fingerprint S3 para deteccao de mudancas.
# MAGIC
# MAGIC **Camada:** Bronze | **Dependencia:** agent_pre | **Output:** `medallion.bronze.conversations`
# MAGIC
# MAGIC _Ultima atualizacao: 2026-04-09_

# COMMAND ----------

# DBTITLE 1,Imports e Setup
import hashlib
import logging
import os
import sys
import time

# Auto-detect repo path from this notebook's location
_nb_path = dbutils.notebook.entry_point.getDbutils().notebook().getContext().notebookPath().get()
_repo_root = "/".join(_nb_path.split("/")[:5])
PIPELINE_ROOT = f"/Workspace{_repo_root}/pipeline"
sys.path.insert(0, PIPELINE_ROOT)

from pipeline_lib.storage import S3Lake

# COMMAND ----------

# DBTITLE 1,Parametros
dbutils.widgets.text("catalog", "medallion", "Catalog Name")
dbutils.widgets.text("scope", "medallion-pipeline", "Secret Scope")
dbutils.widgets.text("bronze_prefix", "bronze/", "Bronze S3 Prefix")

CATALOG = dbutils.widgets.get("catalog")
SCOPE = dbutils.widgets.get("scope")

# Inicializa lake client e logger
lake = S3Lake(dbutils, spark, scope=SCOPE)
logger = logging.getLogger("bronze.ingest")

# COMMAND ----------

# DBTITLE 1,Configuracao de Tabelas
# Prefix do S3 e nome completo da tabela no Unity Catalog
BRONZE_S3_PREFIX = dbutils.widgets.get("bronze_prefix")
BRONZE_TABLE = f"{CATALOG}.bronze.conversations"

# COMMAND ----------

# DBTITLE 1,Verificar Task Values do Agente
# Quando executado dentro do workflow, verifica se o agent_pre autorizou o processamento
try:
    should_process = dbutils.jobs.taskValues.get(
        taskKey="agent_pre", key="should_process", default=True
    )
    if not should_process:
        dbutils.notebook.exit("SKIP: agent decided no processing needed")
    # Usa o prefix definido pelo agent_pre (pode ter sido customizado)
    bronze_prefix = dbutils.jobs.taskValues.get(
        taskKey="agent_pre", key="bronze_prefix", default=BRONZE_S3_PREFIX
    )
except Exception:
    # Execucao standalone sem workflow -- usa prefix do widget
    bronze_prefix = BRONZE_S3_PREFIX
    logger.info("Executando standalone (sem agent_pre)")

# COMMAND ----------

# DBTITLE 1,Ler Parquet do S3
# Marca o inicio para medir duracao total da ingestao
start_time = time.time()

# Le todos os arquivos Parquet do prefix S3 via wrapper boto3
df = lake.read_parquet(bronze_prefix)
row_count = int(df.count())
columns = set(df.columns)

logger.info(f"Linhas lidas: {row_count}")
logger.info(f"Colunas encontradas: {sorted(columns)}")

# COMMAND ----------

# DBTITLE 1,Validar Schema
# Importa o contrato de schema (colunas obrigatorias) e o validador
from pipeline_lib.schema.contracts import REQUIRED_COLUMNS
from pipeline_lib.schema.validator import validate_schema

# Valida as colunas do DataFrame contra o contrato esperado
validation = validate_schema(columns)

if not validation.is_valid:
    # Schema invalido -- seta task values de erro e aborta
    error_msg = f"Schema invalido: {validation.errors}"
    logger.error(error_msg)
    try:
        dbutils.jobs.taskValues.set(key="status", value="FAILED")
        dbutils.jobs.taskValues.set(key="error", value=error_msg)
    except Exception:
        pass
    raise ValueError(error_msg)

# Warnings nao bloqueiam a execucao (ex: colunas extras aceitas via mergeSchema)
if validation.warnings:
    for warning in validation.warnings:
        logger.warning(warning)

# COMMAND ----------

# DBTITLE 1,Salvar como Delta Table e Upload para S3
logger.info(f"Salvando como Delta Table: {BRONZE_TABLE}")

# Salva no Unity Catalog como Delta com merge de schema para colunas novas
(
    df.write
    .format("delta")
    .mode("overwrite")
    .option("mergeSchema", "true")
    .saveAsTable(BRONZE_TABLE)
)

# Verifica contagem apos salvar para garantir integridade
saved_count = int(spark.table(BRONZE_TABLE).count())
logger.info(f"Delta Table salva (UC): {saved_count} linhas")

# Backup em Parquet no S3 para acesso direto
lake.write_parquet(spark.table(BRONZE_TABLE), "bronze/conversations/")
logger.info("Parquet uploaded para S3 bronze/conversations/")

# COMMAND ----------

# DBTITLE 1,Fingerprint via S3 Metadata
def get_s3_fingerprint(prefix: str) -> str:
    """Gera fingerprint dos arquivos no S3 via metadata (boto3).
    Usado para deteccao de mudancas entre execucoes."""
    items = lake.get_metadata(prefix)
    # Ordena por key para hash deterministico
    fingerprint = "|".join(
        f"{item['key']}:{item['size']}:{item['last_modified']}"
        for item in sorted(items, key=lambda x: x["key"])
    )
    return hashlib.sha256(fingerprint.encode()).hexdigest()

try:
    fingerprint = get_s3_fingerprint(bronze_prefix)
    logger.info(f"Fingerprint S3: {fingerprint[:16]}...")
except Exception as e:
    # Fingerprint nao e critico -- usa fallback com contagem de linhas
    fingerprint = f"unknown_{row_count}"
    logger.warning(f"Nao foi possivel calcular fingerprint: {e}")

# COMMAND ----------

# DBTITLE 1,Metricas e Task Values
# Calcula duracao total da ingestao
duration_sec = round(time.time() - start_time, 2)

# Metricas de observabilidade da ingestao
metrics = {
    "rows_input": row_count,
    "rows_output": saved_count,
    "columns_count": len(columns),
    "new_columns": len(columns - REQUIRED_COLUMNS),
    "duration_sec": duration_sec,
    "fingerprint": fingerprint,
}

logger.info(f"Bronze ingestion completa em {duration_sec}s: {metrics}")

# Seta task values para o agent_post coletar
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
    pass

dbutils.notebook.exit(f"SUCCESS: {saved_count} rows ingested in {duration_sec}s")
