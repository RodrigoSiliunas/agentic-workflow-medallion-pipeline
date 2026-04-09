# Databricks notebook source
# MAGIC %md
# MAGIC # Bronze Ingestion - Conversations
# MAGIC Este notebook realiza a ingestão de dados brutos para a camada Bronze

# COMMAND ----------

from pyspark.sql import SparkSession
from pyspark.sql.types import StructType, StructField, StringType
from pyspark.sql.functions import col, current_timestamp, lit
from delta.tables import DeltaTable
import logging

# COMMAND ----------

# Configuração de logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# COMMAND ----------

# Definir schema esperado conforme contrato
expected_schema = StructType([
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

# COMMAND ----------

# Parâmetros
source_path = dbutils.widgets.get("source_path", "s3://data-lake/raw/conversations/")
target_table = "medallion.bronze.conversations"

# COMMAND ----------

def ingest_bronze_data(source_path: str, target_table: str):
    """
    Ingere dados para a camada Bronze com validação de schema
    """
    try:
        # Ler dados de origem
        logger.info(f"Lendo dados de {source_path}")
        df_raw = spark.read \
            .option("multiline", "true") \
            .option("mode", "PERMISSIVE") \
            .json(source_path)
        
        # Verificar colunas extras não esperadas
        raw_columns = set(df_raw.columns)
        expected_columns = set([field.name for field in expected_schema.fields])
        extra_columns = raw_columns - expected_columns
        missing_columns = expected_columns - raw_columns
        
        if extra_columns:
            logger.warning(f"Colunas extras encontradas e serão ignoradas: {extra_columns}")
            # Registrar em tabela de auditoria (opcional)
            audit_df = spark.createDataFrame(
                [(col_name, current_timestamp(), source_path) for col_name in extra_columns],
                ["extra_column", "detected_at", "source_path"]
            )
            audit_df.write.mode("append").saveAsTable("medallion.bronze._audit_extra_columns")
        
        if missing_columns:
            logger.error(f"Colunas obrigatórias faltando: {missing_columns}")
            raise ValueError(f"Schema inválido: colunas faltando {missing_columns}")
        
        # Selecionar apenas colunas válidas do contrato
        valid_columns = [col for col in df_raw.columns if col in expected_columns]
        df_filtered = df_raw.select(*valid_columns)
        
        # Adicionar colunas faltantes com valores nulos
        for col_name in expected_columns:
            if col_name not in df_filtered.columns:
                df_filtered = df_filtered.withColumn(col_name, lit(None).cast(StringType()))
        
        # Garantir ordem das colunas conforme schema
        df_final = df_filtered.select(*[col(field.name) for field in expected_schema.fields])
        
        # Adicionar metadados de ingestão
        df_final = df_final \
            .withColumn("_ingestion_timestamp", current_timestamp()) \
            .withColumn("_source_path", lit(source_path))
        
        # Escrever na tabela Bronze
        logger.info(f"Escrevendo {df_final.count()} registros em {target_table}")
        df_final.write \
            .mode("append") \
            .option("mergeSchema", "false") \
            .saveAsTable(target_table)
        
        logger.info("Ingestão Bronze concluída com sucesso")
        
        # Retornar estatísticas
        return {
            "records_written": df_final.count(),
            "extra_columns_found": list(extra_columns),
            "status": "SUCCESS"
        }
        
    except Exception as e:
        logger.error(f"Erro na ingestão Bronze: {str(e)}")
        raise

# COMMAND ----------

# Executar ingestão
result = ingest_bronze_data(source_path, target_table)

# COMMAND ----------

# Validar resultado
if result["extra_columns_found"]:
    print(f"AVISO: Colunas extras foram encontradas e ignoradas: {result['extra_columns_found']}")
    print("Verifique a tabela medallion.bronze._audit_extra_columns para detalhes")

print(f"Ingestão concluída: {result['records_written']} registros processados")

# COMMAND ----------

# Otimizar tabela Delta
if spark.catalog.tableExists(target_table):
    deltaTable = DeltaTable.forName(spark, target_table)
    deltaTable.optimize().executeCompaction()
    logger.info(f"Tabela {target_table} otimizada")