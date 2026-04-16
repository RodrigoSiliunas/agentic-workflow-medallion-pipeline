# Databricks notebook source
# MAGIC %md
# MAGIC # Bronze Layer - Raw Data Ingestion
# MAGIC Ingestão de dados brutos do WhatsApp para camada Bronze

from pyspark.sql import SparkSession
from pyspark.sql.types import StructType, StructField, StringType
from pyspark.sql.functions import col, current_timestamp, lit
from delta import DeltaTable
import logging

# Setup
spark = SparkSession.builder.appName("BronzeIngestion").getOrCreate()
logger = logging.getLogger(__name__)

# Configuration
SOURCE_PATH = "/mnt/landing/whatsapp/conversations"
TARGET_TABLE = "medallion.bronze.conversations"

# Chaos mode — lido via task value propagado pelo pre_check
chaos_mode = "off"
try:
    chaos_mode = dbutils.jobs.taskValues.get(  # noqa: F821
        taskKey="pre_check", key="chaos_mode", default="off"
    )
except Exception:
    chaos_mode = "off"

# Schema esperado - definição explícita
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
    StructField("metadata", StringType(), True)
])

def validate_and_conform_schema(df, expected_schema):
    """
    Valida e conforma o DataFrame ao schema esperado.
    Remove colunas extras e adiciona colunas faltantes com null.
    """
    expected_cols = [field.name for field in expected_schema.fields]
    actual_cols = df.columns
    
    # Log colunas extras detectadas
    extra_cols = set(actual_cols) - set(expected_cols)
    if extra_cols:
        logger.warning(f"Colunas extras detectadas e serão removidas: {extra_cols}")
        # Remove chaos columns ou qualquer coluna não esperada
        for col_name in extra_cols:
            if col_name.startswith("_chaos_"):
                logger.error(f"CHAOS MODE: Coluna de teste detectada: {col_name}")
                df = df.drop(col_name)
    
    # Adiciona colunas faltantes
    missing_cols = set(expected_cols) - set(actual_cols)
    for col_name in missing_cols:
        logger.warning(f"Coluna faltante será adicionada com NULL: {col_name}")
        df = df.withColumn(col_name, lit(None).cast(StringType()))
    
    # Reordena e seleciona apenas colunas esperadas
    df = df.select(*expected_cols)
    
    return df

def ingest_to_bronze():
    try:
        # Chaos mode: injetar falha controlada para testar Observer Agent
        if chaos_mode == "bronze_schema":
            logger.warning("CHAOS MODE: Injetando bug de schema no Bronze")
            raise ValueError(
                "CHAOS: Schema invalido - coluna _chaos_invalid_col com tipo "
                "incompativel (injetado por chaos_mode=bronze_schema)"
            )

        logger.info(f"Iniciando ingestão Bronze de {SOURCE_PATH}")
        
        # Leitura dos dados
        df_raw = spark.read \
            .option("multiline", "true") \
            .option("inferSchema", "false") \
            .json(SOURCE_PATH)
        
        # Validação e conformação de schema
        df_conformed = validate_and_conform_schema(df_raw, EXPECTED_SCHEMA)
        
        # Adiciona metadados de ingestão
        df_bronze = df_conformed \
            .withColumn("_ingestion_timestamp", current_timestamp()) \
            .withColumn("_source_file", lit(SOURCE_PATH))

        # T5: escreve e usa Delta metadata pra rows — sem count() redundante
        # pre-write (que forçaria full scan do conformed DF).
        df_bronze.write \
            .mode("append") \
            .option("mergeSchema", "false") \
            .saveAsTable(TARGET_TABLE)

        # Validação final via Delta transaction log (O(1), sem scan)
        try:
            detail = spark.sql(f"DESCRIBE DETAIL {TARGET_TABLE}").collect()[0]
            final_count = int(detail["numRows"]) if detail["numRows"] is not None else -1
        except Exception:
            final_count = spark.table(TARGET_TABLE).count()
        logger.info(f"Ingestão concluída. {final_count} registros totais em {TARGET_TABLE}")
        
    except Exception as e:
        logger.error(f"Erro durante ingestão Bronze: {str(e)}")
        # Propagar erro
        if chaos_mode != "off":
            logger.error(f"CHAOS MODE ({chaos_mode}): {e}")
        raise

# COMMAND ----------
# DBTITLE 1,Execucao
ingest_to_bronze()