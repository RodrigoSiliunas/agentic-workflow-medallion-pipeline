# Databricks notebook source
# MAGIC %md
# MAGIC # Bronze Layer - Data Ingestion
# MAGIC This notebook handles raw data ingestion into the bronze layer

# COMMAND ----------

from pyspark.sql import SparkSession
from pyspark.sql.functions import col, current_timestamp, lit, input_file_name
from pyspark.sql.types import *
import json
from datetime import datetime

# COMMAND ----------

# Initialize widgets with default values
dbutils.widgets.text("source_path", "/mnt/data/whatsapp/raw", "Source Path")
dbutils.widgets.text("target_table", "medallion.bronze.conversations", "Target Table")
dbutils.widgets.text("checkpoint_path", "/mnt/checkpoints/bronze", "Checkpoint Path")
dbutils.widgets.text("run_mode", "batch", "Run Mode (batch/streaming)")

# COMMAND ----------

# Get widget values
source_path = dbutils.widgets.get("source_path")
target_table = dbutils.widgets.get("target_table")
checkpoint_path = dbutils.widgets.get("checkpoint_path")
run_mode = dbutils.widgets.get("run_mode")

# COMMAND ----------

# Define schema for bronze conversations table
conversations_schema = StructType([
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

def create_database_if_not_exists():
    """Create medallion database and schema if they don't exist"""
    spark.sql("CREATE DATABASE IF NOT EXISTS medallion")
    spark.sql("CREATE SCHEMA IF NOT EXISTS medallion.bronze")
    print("Database and schema created/verified")

# COMMAND ----------

def ingest_batch_data():
    """Ingest data in batch mode"""
    try:
        # Read raw data - assuming JSON format
        # If CSV, change to spark.read.csv and adjust options
        df = spark.read \
            .option("multiLine", "true") \
            .option("mode", "PERMISSIVE") \
            .option("columnNameOfCorruptRecord", "_corrupt_record") \
            .schema(conversations_schema) \
            .json(f"{source_path}/*.json")
        
        # Add ingestion metadata
        df_with_metadata = df \
            .withColumn("_ingestion_timestamp", current_timestamp()) \
            .withColumn("_source_file", input_file_name())
        
        # Write to bronze table
        df_with_metadata.write \
            .mode("append") \
            .option("mergeSchema", "true") \
            .saveAsTable(target_table)
        
        record_count = df_with_metadata.count()
        print(f"Successfully ingested {record_count} records to {target_table}")
        
        # Log metrics
        log_metrics("bronze_ingestion", record_count, record_count, 0)
        
        return record_count
        
    except Exception as e:
        print(f"Error during batch ingestion: {str(e)}")
        log_metrics("bronze_ingestion", 0, 0, 1)
        raise e

# COMMAND ----------

def ingest_streaming_data():
    """Ingest data in streaming mode"""
    try:
        # Read streaming data
        stream_df = spark.readStream \
            .option("multiLine", "true") \
            .option("mode", "PERMISSIVE") \
            .schema(conversations_schema) \
            .json(source_path)
        
        # Add ingestion metadata
        stream_df_with_metadata = stream_df \
            .withColumn("_ingestion_timestamp", current_timestamp()) \
            .withColumn("_source_file", input_file_name())
        
        # Write streaming data
        query = stream_df_with_metadata.writeStream \
            .outputMode("append") \
            .option("checkpointLocation", f"{checkpoint_path}/bronze_conversations") \
            .trigger(processingTime='10 seconds') \
            .table(target_table)
        
        # Wait for termination signal
        query.awaitTermination()
        
    except Exception as e:
        print(f"Error during streaming ingestion: {str(e)}")
        raise e

# COMMAND ----------

def log_metrics(task_name, rows_input, rows_output, rows_error):
    """Log pipeline metrics"""
    try:
        metrics_df = spark.createDataFrame([
            {
                "task": task_name,
                "run_id": spark.conf.get("spark.databricks.job.runId", "local_run"),
                "timestamp": datetime.now().isoformat(),
                "rows_input": rows_input,
                "rows_output": rows_output,
                "rows_error": rows_error,
                "duration_sec": 0.0  # Will be calculated by orchestrator
            }
        ])
        
        metrics_df.write \
            .mode("append") \
            .saveAsTable("medallion.pipeline.metrics")
            
    except Exception as e:
        print(f"Warning: Failed to log metrics: {str(e)}")
        # Don't fail the pipeline due to metrics logging failure

# COMMAND ----------

# Main execution
try:
    # Create database and schema
    create_database_if_not_exists()
    
    # Create bronze table if not exists
    spark.sql(f"""
        CREATE TABLE IF NOT EXISTS {target_table} (
            message_id STRING,
            conversation_id STRING,
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
        LOCATION '/mnt/delta/medallion/bronze/conversations'
    """)
    
    # Run ingestion based on mode
    if run_mode == "streaming":
        print("Starting streaming ingestion...")
        ingest_streaming_data()
    else:
        print("Starting batch ingestion...")
        record_count = ingest_batch_data()
        
        # Update pipeline state
        state_df = spark.createDataFrame([{
            "run_at": datetime.now().isoformat(),
            "last_bronze_hash": str(record_count),  # Simple hash based on count
            "status": "bronze_completed",
            "consecutive_failures": 0,
            "delta_versions": json.dumps({"bronze.conversations": 1})
        }])
        
        state_df.write \
            .mode("overwrite") \
            .saveAsTable("medallion.pipeline.state")
    
    print("Bronze ingestion completed successfully")
    
except Exception as e:
    error_msg = f"Bronze ingestion failed: {str(e)}"
    print(error_msg)
    
    # Log error notification
    try:
        notification_df = spark.createDataFrame([{
            "timestamp": datetime.now().isoformat(),
            "level": "ERROR",
            "subject": "Bronze Ingestion Failed",
            "body": error_msg,
            "run_id": spark.conf.get("spark.databricks.job.runId", "local_run")
        }])
        
        notification_df.write \
            .mode("append") \
            .saveAsTable("medallion.pipeline.notifications")
    except:
        pass
    
    raise e

# COMMAND ----------

# Return success
dbutils.notebook.exit("SUCCESS")