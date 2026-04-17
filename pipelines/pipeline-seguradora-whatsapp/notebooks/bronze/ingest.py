# Databricks notebook source
# MAGIC %md
# MAGIC # Bronze Layer - Raw Data Ingestion
# MAGIC Ingestão de dados brutos do WhatsApp para camada Bronze.
# MAGIC
# MAGIC **Input**: JSON multi-line em `/mnt/landing/whatsapp/conversations`
# MAGIC **Output**: `medallion.bronze.conversations` (Delta, append mode)
# MAGIC **Schema evolution**: `mergeSchema=false` — schema explicito via EXPECTED_SCHEMA.

# COMMAND ----------
# DBTITLE 1,Imports
import logging
import sys

from delta import DeltaTable  # noqa: F401
from pyspark.sql import SparkSession
from pyspark.sql.functions import col, current_timestamp, lit  # noqa: F401
from pyspark.sql.types import StringType, StructField, StructType

# COMMAND ----------
# DBTITLE 1,Setup Spark + Logger
spark = SparkSession.builder.appName("BronzeIngestion").getOrCreate()
logger = logging.getLogger(__name__)

# COMMAND ----------
# DBTITLE 1,Auto-detect repo root para importar pipeline_lib
_nb_path = dbutils.notebook.entry_point.getDbutils().notebook().getContext().notebookPath().get()  # noqa: F821
_repo_root = "/".join(_nb_path.split("/")[:4])
PIPELINE_ROOT = f"/Workspace{_repo_root}/pipelines/pipeline-seguradora-whatsapp"
sys.path.insert(0, PIPELINE_ROOT)

from pipeline_lib.schema import conform_to_schema  # noqa: NB003, E402
from pipeline_lib.validation import delta_row_count  # noqa: NB003, E402, F401

# COMMAND ----------
# DBTITLE 1,Configuration
SOURCE_PATH = "/mnt/landing/whatsapp/conversations"
TARGET_TABLE = "medallion.bronze.conversations"

# COMMAND ----------
# DBTITLE 1,Chaos mode — propagado via task value do pre_check
chaos_mode = "off"
try:
    chaos_mode = dbutils.jobs.taskValues.get(  # noqa: F821
        taskKey="pre_check", key="chaos_mode", default="off"
    )
except Exception:
    chaos_mode = "off"

# COMMAND ----------
# DBTITLE 1,Schema esperado — definicao explicita
EXPECTED_SCHEMA = StructType([
    StructField("message_id", StringType(), True),
    StructField("conversation_id", StringType(), True),
    StructField("timestamp", StringType(), True),
    StructField("direction", StringType(), True),
    StructField("sender_phone", StringType(), True),
    StructField("sender_name", StringType(), True),
    StructField("message_type", StringType(), True),
    StructField("message_body", StringType(), True),
    StructField("status", StringType(), True),
    StructField("channel", StringType(), True),
    StructField("campaign_id", StringType(), True),
    StructField("agent_id", StringType(), True),
    StructField("conversation_outcome", StringType(), True),
    StructField("metadata", StringType(), True),
])

# COMMAND ----------
# DBTITLE 1,Funcao principal de ingestao
def ingest_to_bronze():
    try:
        # Chaos mode: injetar falha controlada para testar Observer Agent
        if chaos_mode == "bronze_schema":
            logger.warning("CHAOS MODE: Injetando bug de schema no Bronze")
            raise ValueError(
                "CHAOS: Schema invalido - coluna _chaos_invalid_col com tipo "
                "incompativel (injetado por chaos_mode=bronze_schema)"
            )

        logger.info(f"Iniciando ingestao Bronze de {SOURCE_PATH}")

        # Leitura dos dados
        df_raw = (
            spark.read
            .option("multiline", "true")
            .option("inferSchema", "false")
            .json(SOURCE_PATH)
        )

        # Validacao e conformacao de schema (pipeline_lib — testado)
        df_conformed = conform_to_schema(df_raw, EXPECTED_SCHEMA)

        # Adiciona metadados de ingestao
        df_bronze = (
            df_conformed
            .withColumn("_ingestion_timestamp", current_timestamp())
            .withColumn("_source_file", lit(SOURCE_PATH))
        )

        # Escrita Delta (append) sem count() pre-write redundante
        df_bronze.write \
            .mode("append") \
            .option("mergeSchema", "false") \
            .saveAsTable(TARGET_TABLE)

        # Validacao final via Delta transaction log (O(1), sem scan)
        try:
            detail = spark.sql(f"DESCRIBE DETAIL {TARGET_TABLE}").collect()[0]
            final_count = int(detail["numRows"]) if detail["numRows"] is not None else -1
        except Exception:
            final_count = spark.table(TARGET_TABLE).count()
        logger.info(f"Ingestao concluida. {final_count} registros totais em {TARGET_TABLE}")

    except Exception as e:
        logger.error(f"Erro durante ingestao Bronze: {str(e)}")
        if chaos_mode != "off":
            logger.error(f"CHAOS MODE ({chaos_mode}): {e}")
        raise

# COMMAND ----------
# DBTITLE 1,Execucao
ingest_to_bronze()
