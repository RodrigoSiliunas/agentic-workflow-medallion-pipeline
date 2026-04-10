# Databricks notebook source
# MAGIC %md
# MAGIC # Silver Layer - Deduplication and Cleaning
# MAGIC This notebook deduplicates messages and performs additional cleaning

# COMMAND ----------

from pyspark.sql import SparkSession, Window
from pyspark.sql.functions import (
    col, row_number, desc, asc, when, isnan, isnull,
    trim, upper, lower, regexp_replace, coalesce,
    current_timestamp, lit
)
from delta.tables import DeltaTable
import logging
from datetime import datetime

# COMMAND ----------

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# COMMAND ----------

# Widget setup with proper error handling
try:
    dbutils.widgets.text("catalog", "medallion", "Catalog")
    dbutils.widgets.text("run_id", "", "Run ID")
    dbutils.widgets.text("run_at", "", "Run Timestamp")
except Exception as e:
    logger.warning(f"Widgets might already exist: {e}")

# Get widget values safely
catalog = dbutils.widgets.get("catalog")
run_id = dbutils.widgets.get("run_id")
run_at = dbutils.widgets.get("run_at")

# COMMAND ----------

# Configuration
BRONZE_TABLE = f"{catalog}.bronze.conversations"
SILVER_MESSAGES = f"{catalog}.silver.messages_clean"
METRICS_TABLE = f"{catalog}.pipeline.metrics"

# COMMAND ----------

# Validate tables exist
try:
    spark.table(BRONZE_TABLE).limit(1).count()
    logger.info(f"Successfully validated bronze table: {BRONZE_TABLE}")
except Exception as e:
    logger.error(f"Bronze table {BRONZE_TABLE} not accessible: {e}")
    raise

try:
    spark.table(SILVER_MESSAGES).limit(1).count()
    logger.info(f"Successfully validated silver table: {SILVER_MESSAGES}")
except Exception as e:
    logger.error(f"Silver table {SILVER_MESSAGES} not accessible: {e}")
    raise

# COMMAND ----------

# Read data from silver messages table
start_time = datetime.now()
logger.info(f"Starting deduplication process for run_id: {run_id}")

# Read silver messages
silver_df = spark.table(SILVER_MESSAGES)
rows_input = silver_df.count()
logger.info(f"Loaded {rows_input} rows from silver messages table")

# COMMAND ----------

# Define deduplication window
# Deduplicate by message_id, keeping the most recent version based on timestamp
window_spec = Window.partitionBy("message_id").orderBy(desc("timestamp"))

# Apply deduplication
deduped_df = silver_df \
    .withColumn("row_num", row_number().over(window_spec)) \
    .filter(col("row_num") == 1) \
    .drop("row_num")

rows_after_dedup = deduped_df.count()
logger.info(f"Rows after deduplication: {rows_after_dedup} (removed {rows_input - rows_after_dedup} duplicates)")

# COMMAND ----------

# Additional cleaning steps
# Remove any messages with null or empty message_id
cleaned_df = deduped_df.filter(
    col("message_id").isNotNull() & 
    (col("message_id") != "")
)

# Ensure conversation_id is not null
cleaned_df = cleaned_df.filter(
    col("conversation_id").isNotNull() & 
    (col("conversation_id") != "")
)

# Clean up message body - remove excessive whitespace
cleaned_df = cleaned_df.withColumn(
    "message_body",
    when(col("message_body").isNotNull(), 
         regexp_replace(trim(col("message_body")), r"\s+", " ")
    ).otherwise(col("message_body"))
)

rows_output = cleaned_df.count()
rows_error = rows_after_dedup - rows_output
logger.info(f"Final row count after cleaning: {rows_output}")

# COMMAND ----------

# Write back to silver messages table using merge
try:
    # Use merge to update existing records and insert new ones
    silver_table = DeltaTable.forName(spark, SILVER_MESSAGES)
    
    silver_table.alias("target").merge(
        cleaned_df.alias("source"),
        "target.message_id = source.message_id"
    ).whenMatchedUpdateAll().whenNotMatchedInsertAll().execute()
    
    logger.info("Successfully updated silver messages table with deduplicated data")
except Exception as e:
    logger.error(f"Error writing to silver table: {e}")
    # If merge fails, try overwrite as fallback
    logger.info("Attempting overwrite as fallback")
    cleaned_df.write.mode("overwrite").option("overwriteSchema", "false").saveAsTable(SILVER_MESSAGES)

# COMMAND ----------

# Log metrics
duration = (datetime.now() - start_time).total_seconds()

metrics_df = spark.createDataFrame([{
    "task": "silver_dedup",
    "run_id": run_id,
    "timestamp": run_at,
    "rows_input": rows_input,
    "rows_output": rows_output,
    "rows_error": rows_error,
    "duration_sec": duration
}])

metrics_df.write.mode("append").saveAsTable(METRICS_TABLE)
logger.info(f"Metrics logged: input={rows_input}, output={rows_output}, errors={rows_error}, duration={duration}s")

# COMMAND ----------

# Optimize table
try:
    spark.sql(f"OPTIMIZE {SILVER_MESSAGES}")
    logger.info("Table optimized successfully")
except Exception as e:
    logger.warning(f"Could not optimize table: {e}")

# COMMAND ----------

# Return success
dbutils.notebook.exit(json.dumps({
    "status": "success",
    "rows_processed": rows_output,
    "duplicates_removed": rows_input - rows_after_dedup,
    "duration_seconds": duration
}))