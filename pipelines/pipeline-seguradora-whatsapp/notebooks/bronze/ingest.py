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
CHAOS_MODE_ENABLED = False  # Desabilitar chaos mode em produção
SOURCE_PATH = "/mnt/landing/whatsapp/conversations"
TARGET_TABLE = "medallion.bronze.conversations"

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
                if not CHAOS_MODE_ENABLED:
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
        
        # Log estatísticas
        total_records = df_bronze.count()
        logger.info(f"Total de registros a ingerir: {total_records}")
        
        # Escreve na tabela Bronze
        df_bronze.write \
            .mode("append") \
            .option("mergeSchema", "false") \
            .saveAsTable(TARGET_TABLE)
        
        logger.info(f"Ingestão concluída com sucesso. {total_records} registros gravados em {TARGET_TABLE}")
        
        # Validação final
        final_count = spark.table(TARGET_TABLE).count()
        logger.info(f"Total de registros na tabela após ingestão: {final_count}")
        
    except Exception as e:
        logger.error(f"Erro durante ingestão Bronze: {str(e)}")
        # Se for erro de chaos mode em produção, falha com mensagem clara
        if "_chaos_" in str(e) and not CHAOS_MODE_ENABLED:
            raise ValueError("Chaos mode detectado em produção. Desabilite o chaos engineering ou ative CHAOS_MODE_ENABLED")
        raise

# Execução principal
if __name__ == "__main__":
    ingest_to_bronze()
    print("Bronze ingestion completed successfully")