# Bronze Ingestion Notebook
# Responsável por ingerir dados raw do WhatsApp para camada Bronze

from pyspark.sql import SparkSession
from pyspark.sql.functions import col, current_timestamp, lit
from delta.tables import DeltaTable
import json

# Initialize Spark Session
spark = SparkSession.builder.appName("BronzeIngestion").getOrCreate()

# Define expected schema columns
EXPECTED_COLUMNS = [
    "message_id",
    "conversation_id", 
    "timestamp",
    "direction",
    "sender_phone",
    "sender_name",
    "message_type",
    "message_body",
    "status",
    "channel",
    "campaign_id",
    "agent_id",
    "conversation_outcome",
    "metadata"
]

# Read raw data
raw_data_path = "/mnt/raw/whatsapp/conversations"
bronze_table_path = "/mnt/medallion/bronze/conversations"

try:
    # Read raw data
    df_raw = spark.read.format("json").load(raw_data_path)
    
    # Remove any columns not in expected schema
    df_cleaned = df_raw.select(*[col(c) for c in EXPECTED_COLUMNS if c in df_raw.columns])
    
    # Add any missing columns with null values
    for column in EXPECTED_COLUMNS:
        if column not in df_cleaned.columns:
            df_cleaned = df_cleaned.withColumn(column, lit(None).cast("string"))
    
    # Ensure correct column order
    df_final = df_cleaned.select(*EXPECTED_COLUMNS)
    
    # Add ingestion metadata
    df_final = df_final.withColumn("_ingestion_timestamp", current_timestamp())
    
    # Write to Bronze table
    (
        df_final.write
        .format("delta")
        .mode("append")
        .option("mergeSchema", "false")  # Explicitly disable schema merge
        .save(bronze_table_path)
    )
    
    # Log metrics
    rows_processed = df_final.count()
    print(f"Successfully ingested {rows_processed} rows to Bronze layer")
    
    # Update pipeline metrics
    metrics_df = spark.createDataFrame([
        {
            "task": "bronze_ingestion",
            "run_id": spark.conf.get("spark.databricks.job.runId", "local"),
            "timestamp": current_timestamp(),
            "rows_input": df_raw.count(),
            "rows_output": rows_processed,
            "rows_error": 0,
            "duration_sec": 0.0  # Will be calculated by orchestrator
        }
    ])
    
    metrics_df.write.format("delta").mode("append").save("/mnt/medallion/pipeline/metrics")
    
except Exception as e:
    print(f"Error during Bronze ingestion: {str(e)}")
    
    # Log error metrics
    error_metrics_df = spark.createDataFrame([
        {
            "task": "bronze_ingestion",
            "run_id": spark.conf.get("spark.databricks.job.runId", "local"),
            "timestamp": current_timestamp(),
            "rows_input": 0,
            "rows_output": 0,
            "rows_error": 1,
            "duration_sec": 0.0
        }
    ])
    
    error_metrics_df.write.format("delta").mode("append").save("/mnt/medallion/pipeline/metrics")
    
    # Re-raise the exception
    raise e