# Databricks notebook source
# MAGIC %md
# MAGIC # Bronze Layer - Raw Data Ingestion
# MAGIC This notebook ingests raw WhatsApp conversation data into the bronze layer

from pyspark.sql import SparkSession
from pyspark.sql.functions import (
    current_timestamp, 
    input_file_name,
    col,
    when,
    lit
)
from pyspark.sql.types import (
    StructType, 
    StructField, 
    StringType, 
    TimestampType
)
import logging
from delta.tables import DeltaTable

# Initialize Spark session
spark = SparkSession.builder.appName("BronzeIngestion").getOrCreate()
logger = logging.getLogger(__name__)

# COMMAND ----------

# Configuration
SOURCE_PATH = "/mnt/raw/whatsapp/conversations/"
TARGET_TABLE = "medallion.bronze.conversations"
CHECKPOINT_PATH = "/mnt/checkpoints/bronze/conversations"

# IMPORTANTE: Desabilitar chaos mode para produção
CHAOS_MODE_ENABLED = False  # Mudança crítica: estava True ou ativado via parâmetro

# COMMAND ----------

# Define expected schema for bronze layer
bronze_schema = StructType([
    StructField("message_id", StringType(), False),
    StructField("conversation_id", StringType(), False),
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

def validate_schema(df, expected_schema):
    """
    Validate DataFrame schema against expected schema
    """
    actual_fields = {f.name: f.dataType for f in df.schema.fields}
    expected_fields = {f.name: f.dataType for f in expected_schema.fields}
    
    # Check for missing required fields
    missing_fields = set(expected_fields.keys()) - set(actual_fields.keys())
    if missing_fields:
        logger.warning(f"Missing required fields: {missing_fields}")
        # Add missing fields with null values
        for field_name in missing_fields:
            df = df.withColumn(field_name, lit(None).cast(expected_fields[field_name]))
    
    # Remove extra fields not in schema
    extra_fields = set(actual_fields.keys()) - set(expected_fields.keys())
    if extra_fields:
        logger.warning(f"Removing extra fields not in schema: {extra_fields}")
        df = df.select(*[col(f.name) for f in expected_schema.fields])
    
    return df

# COMMAND ----------

def ingest_bronze_data():
    """
    Main ingestion function for bronze layer
    """
    try:
        logger.info(f"Starting bronze ingestion from {SOURCE_PATH}")
        
        # Read raw data
        raw_df = (
            spark.readStream
            .format("json")
            .option("multiline", "true")
            .option("mode", "PERMISSIVE")
            .option("columnNameOfCorruptRecord", "_corrupt_record")
            .schema(bronze_schema)
            .load(SOURCE_PATH)
        )
        
        # Add ingestion metadata
        bronze_df = (
            raw_df
            .withColumn("_ingestion_timestamp", current_timestamp())
            .withColumn("_source_file", input_file_name())
        )
        
        # Validate and fix schema
        bronze_df = validate_schema(bronze_df, bronze_schema)
        
        # Filter out corrupt records
        bronze_df = bronze_df.filter(col("_corrupt_record").isNull() | (col("_corrupt_record") == ""))
        bronze_df = bronze_df.drop("_corrupt_record") if "_corrupt_record" in bronze_df.columns else bronze_df
        
        # Write to Delta table
        query = (
            bronze_df.writeStream
            .format("delta")
            .outputMode("append")
            .option("checkpointLocation", CHECKPOINT_PATH)
            .option("mergeSchema", "false")  # Strict schema enforcement
            .trigger(availableNow=True)
            .table(TARGET_TABLE)
        )
        
        # Wait for completion
        query.awaitTermination()
        
        # Log success metrics
        record_count = spark.table(TARGET_TABLE).count()
        logger.info(f"Bronze ingestion completed successfully. Total records: {record_count}")
        
    except Exception as e:
        logger.error(f"Error during bronze ingestion: {str(e)}")
        # Re-raise after logging
        raise

# COMMAND ----------

# Create table if not exists
spark.sql(f"""
    CREATE TABLE IF NOT EXISTS {TARGET_TABLE} (
        message_id STRING NOT NULL,
        conversation_id STRING NOT NULL,
        timestamp STRING,
        direction STRING,
        sender_phone STRING,
        sender_name STRING,
        message_type STRING,
        message_body STRING,
        status STRING,
        channel STRING,
        campaign_id STRING,
        agent_id STRING,
        conversation_outcome STRING,
        metadata STRING,
        _ingestion_timestamp TIMESTAMP,
        _source_file STRING
    )
    USING DELTA
    LOCATION '/mnt/delta/bronze/conversations'
""")

# COMMAND ----------

# Execute ingestion
if __name__ == "__main__":
    ingest_bronze_data()
    
    # Optimize table after ingestion
    spark.sql(f"OPTIMIZE {TARGET_TABLE} ZORDER BY (conversation_id, timestamp)")
    
    # Display sample data for validation
    display(spark.table(TARGET_TABLE).limit(10))