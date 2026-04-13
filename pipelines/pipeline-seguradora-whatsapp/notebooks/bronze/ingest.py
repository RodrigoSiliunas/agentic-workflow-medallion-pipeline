# Databricks notebook source
# MAGIC %md
# MAGIC # Bronze Layer - Raw Data Ingestion
# MAGIC 
# MAGIC Este notebook ingere dados raw de conversas WhatsApp para a camada Bronze

# COMMAND ----------

# MAGIC %pip install delta-spark

# COMMAND ----------

import json
import logging
from datetime import datetime
from typing import Dict, Any, Optional

from pyspark.sql import SparkSession, DataFrame
from pyspark.sql.functions import (
    col, current_timestamp, lit, input_file_name,
    from_json, schema_of_json
)
from pyspark.sql.types import StructType, StructField, StringType
from delta.tables import DeltaTable

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# COMMAND ----------

# Configuration
BRONZE_TABLE = "medallion.bronze.conversations"
SOURCE_PATH = "/mnt/landing/whatsapp/conversations/"  # Adjust based on your source
CHECKPOINT_PATH = "/mnt/checkpoints/bronze/conversations/"

# COMMAND ----------

def create_bronze_schema() -> StructType:
    """
    Define the schema for the bronze conversations table.
    """
    return StructType([
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

def ingest_to_bronze(
    spark: SparkSession,
    source_path: str = SOURCE_PATH,
    target_table: str = BRONZE_TABLE,
    checkpoint_path: str = CHECKPOINT_PATH,
    batch_mode: bool = False
) -> None:
    """
    Ingest raw data from source to Bronze layer.
    
    Args:
        spark: SparkSession
        source_path: Path to source data
        target_table: Target Delta table name
        checkpoint_path: Checkpoint location for streaming
        batch_mode: If True, run as batch; if False, run as streaming
    """
    logger.info(f"Starting ingestion to {target_table}")
    
    try:
        # Create schema
        schema = create_bronze_schema()
        
        # Read source data
        if batch_mode:
            # Batch mode - read all files at once
            df = (spark.read
                  .format("json")
                  .schema(schema)
                  .option("multiLine", "true")
                  .load(source_path))
            
            # Add metadata columns
            df = df.withColumn("_ingested_at", current_timestamp()) \
                   .withColumn("_source_file", input_file_name())
            
            # Write to Bronze table
            df.write \
              .mode("append") \
              .format("delta") \
              .saveAsTable(target_table)
            
            logger.info(f"Batch ingestion completed. Rows written: {df.count()}")
            
        else:
            # Streaming mode - continuous ingestion
            stream_df = (spark.readStream
                        .format("json")
                        .schema(schema)
                        .option("multiLine", "true")
                        .option("maxFilesPerTrigger", 100)
                        .load(source_path))
            
            # Add metadata columns
            stream_df = stream_df.withColumn("_ingested_at", current_timestamp()) \
                                 .withColumn("_source_file", input_file_name())
            
            # Write stream to Bronze table
            query = (stream_df.writeStream
                    .format("delta")
                    .outputMode("append")
                    .option("checkpointLocation", checkpoint_path)
                    .trigger(processingTime="10 seconds")
                    .table(target_table))
            
            # For batch jobs, wait for one micro-batch and stop
            if batch_mode:
                query.processAllAvailable()
                query.stop()
            
            logger.info("Streaming ingestion started successfully")
    
    except Exception as e:
        logger.error(f"Error during ingestion: {str(e)}")
        raise

# COMMAND ----------

def validate_bronze_data(spark: SparkSession, table_name: str = BRONZE_TABLE) -> Dict[str, Any]:
    """
    Validate the bronze table data quality.
    """
    df = spark.table(table_name)
    
    validation_results = {
        "total_rows": df.count(),
        "null_message_ids": df.filter(col("message_id").isNull()).count(),
        "null_conversation_ids": df.filter(col("conversation_id").isNull()).count(),
        "unique_conversations": df.select("conversation_id").distinct().count(),
        "unique_agents": df.select("agent_id").distinct().count(),
        "unique_campaigns": df.select("campaign_id").distinct().count()
    }
    
    logger.info(f"Validation results: {validation_results}")
    return validation_results

# COMMAND ----------

# Main execution
if __name__ == "__main__":
    # Initialize Spark session
    spark = SparkSession.builder \
        .appName("Bronze_Ingestion") \
        .config("spark.sql.extensions", "io.delta.sql.DeltaSparkSessionExtension") \
        .config("spark.sql.catalog.spark_catalog", "org.apache.spark.sql.delta.catalog.DeltaCatalog") \
        .getOrCreate()
    
    # Set up database
    spark.sql("CREATE DATABASE IF NOT EXISTS medallion")
    spark.sql("CREATE SCHEMA IF NOT EXISTS medallion.bronze")
    
    # Run ingestion in batch mode
    ingest_to_bronze(spark, batch_mode=True)
    
    # Validate data
    validation_results = validate_bronze_data(spark)
    
    # Display results
    display(spark.table(BRONZE_TABLE).limit(10))
    print(f"\nValidation Results: {json.dumps(validation_results, indent=2)}")