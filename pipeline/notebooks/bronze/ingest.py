# Databricks notebook source
# MAGIC %md
# MAGIC # Bronze Layer - Data Ingestion
# MAGIC Ingests raw WhatsApp conversation data into Bronze layer

from pyspark.sql import SparkSession
from pyspark.sql.functions import col, current_timestamp, lit
from delta.tables import DeltaTable
import json

spark = SparkSession.builder.appName("BronzeIngestion").getOrCreate()

# COMMAND ----------

# Configuration
BRONZE_PATH = "/mnt/delta/medallion/bronze/conversations"
SOURCE_PATH = "/mnt/landing/whatsapp/conversations"

# Expected schema columns
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

# COMMAND ----------

# Read raw data
print(f"Reading data from: {SOURCE_PATH}")
raw_df = spark.read.option("multiline", "true").json(SOURCE_PATH)

# Log schema information
print("Raw data schema:")
raw_df.printSchema()

# Check for unexpected columns
raw_columns = set(raw_df.columns)
expected_columns_set = set(EXPECTED_COLUMNS)
extra_columns = raw_columns - expected_columns_set
missing_columns = expected_columns_set - raw_columns

if extra_columns:
    print(f"WARNING: Found unexpected columns that will be ignored: {extra_columns}")
    # Log to metrics table for monitoring
    spark.sql(f"""
        INSERT INTO medallion.pipeline.notifications 
        VALUES (
            '{current_timestamp()}',
            'WARNING',
            'Unexpected columns in bronze ingestion',
            'Extra columns found: {json.dumps(list(extra_columns))}',
            '{spark.sparkContext.applicationId}'
        )
    """)

if missing_columns:
    print(f"ERROR: Missing required columns: {missing_columns}")
    raise ValueError(f"Missing required columns in source data: {missing_columns}")

# COMMAND ----------

# Select only expected columns to ensure schema consistency
print("Selecting expected columns...")
selected_df = raw_df.select(*[col(c) for c in EXPECTED_COLUMNS])

# Add ingestion metadata
bronze_df = selected_df \
    .withColumn("_ingestion_timestamp", current_timestamp()) \
    .withColumn("_source_file", lit(SOURCE_PATH))

# COMMAND ----------

# Write to Bronze layer
print(f"Writing {bronze_df.count()} records to Bronze layer...")

if DeltaTable.isDeltaTable(spark, BRONZE_PATH):
    # Merge new data
    bronze_table = DeltaTable.forPath(spark, BRONZE_PATH)
    bronze_table.alias("target").merge(
        bronze_df.alias("source"),
        "target.message_id = source.message_id"
    ).whenMatchedUpdateAll().whenNotMatchedInsertAll().execute()
else:
    # Create new table
    bronze_df.write \
        .format("delta") \
        .mode("overwrite") \
        .option("overwriteSchema", "true") \
        .save(BRONZE_PATH)
    
    # Create table in metastore
    spark.sql(f"""
        CREATE TABLE IF NOT EXISTS medallion.bronze.conversations
        USING DELTA
        LOCATION '{BRONZE_PATH}'
    """)

# COMMAND ----------

# Log metrics
records_written = bronze_df.count()
print(f"Successfully wrote {records_written} records to Bronze layer")

spark.sql(f"""
    INSERT INTO medallion.pipeline.metrics
    VALUES (
        'bronze_ingestion',
        '{spark.sparkContext.applicationId}',
        '{current_timestamp()}',
        {records_written},
        {records_written},
        0,
        {spark.sparkContext.statusTracker().getExecutorInfos().__len__()}
    )
""")

# COMMAND ----------

# Validate Bronze table
bronze_validation = spark.sql("SELECT COUNT(*) as cnt FROM medallion.bronze.conversations")
print(f"Bronze table now contains {bronze_validation.collect()[0]['cnt']} records")

# Return success
dbutils.notebook.exit(json.dumps({
    "status": "success",
    "records_processed": records_written,
    "extra_columns_ignored": list(extra_columns) if extra_columns else []
}))