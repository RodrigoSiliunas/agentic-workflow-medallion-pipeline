# Databricks notebook source
# MAGIC %md
# MAGIC # Bronze Layer - Data Ingestion
# MAGIC Este notebook realiza a ingestão de dados para a camada bronze

# COMMAND ----------

from pyspark.sql import SparkSession
from pyspark.sql.functions import current_timestamp, input_file_name, col
from delta import DeltaTable
import logging

# COMMAND ----------

# Configuração de logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# COMMAND ----------

# Parâmetros do notebook
dbutils.widgets.text("source_path", "", "Source Path")
dbutils.widgets.text("catalog", "medallion", "Catalog Name")
dbutils.widgets.text("schema", "bronze", "Schema Name")
dbutils.widgets.text("table", "whatsapp_raw", "Table Name")

source_path = dbutils.widgets.get("source_path")
catalog = dbutils.widgets.get("catalog")
schema = dbutils.widgets.get("schema")
table_name = dbutils.widgets.get("table")

# COMMAND ----------

# Verificar se temos permissões no catálogo
try:
    spark.sql(f"USE CATALOG {catalog}")
    logger.info(f"Successfully accessed catalog: {catalog}")
except Exception as e:
    logger.error(f"Cannot access catalog {catalog}: {str(e)}")
    logger.error("Please ensure the user has BROWSE permission on the catalog")
    # Tentar criar o catálogo se não existir (requer CREATE CATALOG permission)
    try:
        spark.sql(f"CREATE CATALOG IF NOT EXISTS {catalog}")
        spark.sql(f"USE CATALOG {catalog}")
        logger.info(f"Created and switched to catalog: {catalog}")
    except Exception as create_error:
        logger.error(f"Cannot create catalog: {str(create_error)}")
        raise Exception(f"Insufficient permissions on catalog '{catalog}'. Please contact your administrator to grant: USE, BROWSE, CREATE permissions")

# COMMAND ----------

# Criar schema se não existir
try:
    spark.sql(f"CREATE SCHEMA IF NOT EXISTS {schema}")
    spark.sql(f"USE SCHEMA {schema}")
    logger.info(f"Using schema: {catalog}.{schema}")
except Exception as e:
    logger.error(f"Cannot create/use schema: {str(e)}")
    raise

# COMMAND ----------

# Função para ingerir dados
def ingest_to_bronze(source_path, target_table):
    """
    Realiza a ingestão de dados para a camada bronze
    """
    try:
        # Verificar se o caminho de origem existe
        if not source_path:
            raise ValueError("Source path is empty")
            
        # Ler dados da origem
        logger.info(f"Reading data from: {source_path}")
        
        # Assumindo formato JSON - ajustar conforme necessário
        df = (
            spark.read
            .option("multiline", "true")
            .option("inferSchema", "true")
            .json(source_path)
        )
        
        # Adicionar metadados de auditoria
        df_with_metadata = (
            df
            .withColumn("_ingestion_timestamp", current_timestamp())
            .withColumn("_source_file", input_file_name())
        )
        
        # Salvar na tabela Delta
        full_table_name = f"{catalog}.{schema}.{target_table}"
        logger.info(f"Writing data to: {full_table_name}")
        
        # Verificar se a tabela existe
        if spark.catalog.tableExists(full_table_name):
            # Append aos dados existentes
            df_with_metadata.write \
                .mode("append") \
                .option("mergeSchema", "true") \
                .saveAsTable(full_table_name)
        else:
            # Criar nova tabela
            df_with_metadata.write \
                .mode("overwrite") \
                .option("overwriteSchema", "true") \
                .saveAsTable(full_table_name)
        
        # Otimizar a tabela
        spark.sql(f"OPTIMIZE {full_table_name}")
        
        # Registrar estatísticas
        count = spark.table(full_table_name).count()
        logger.info(f"Successfully ingested data. Total records in table: {count}")
        
        return count
        
    except Exception as e:
        logger.error(f"Error during ingestion: {str(e)}")
        raise

# COMMAND ----------

# Executar ingestão
try:
    if not source_path:
        raise ValueError("source_path parameter is required")
        
    records_ingested = ingest_to_bronze(source_path, table_name)
    
    # Retornar resultado para o workflow
    dbutils.notebook.exit({
        "status": "success",
        "records_ingested": records_ingested,
        "table": f"{catalog}.{schema}.{table_name}"
    })
    
except Exception as e:
    logger.error(f"Bronze ingestion failed: {str(e)}")
    dbutils.notebook.exit({
        "status": "failed",
        "error": str(e)
    })