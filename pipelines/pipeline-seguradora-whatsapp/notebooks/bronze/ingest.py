# Databricks notebook source
# MAGIC %md
# MAGIC ## Bronze Layer - Data Ingestion
# MAGIC Ingests raw data from source systems into Bronze layer

from pyspark.sql import SparkSession
from pyspark.sql.types import *
from pyspark.sql.functions import *
from delta.tables import *
import logging
from datetime import datetime

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# COMMAND ----------

# Configuration
SOURCE_PATH = "/mnt/landing/whatsapp/messages"  # Adjust based on your actual source
BRONZE_PATH = "/mnt/bronze/whatsapp_messages"
CHECKPOINT_PATH = "/mnt/checkpoints/bronze/whatsapp_messages"

# COMMAND ----------

# Define explicit schema for WhatsApp messages
# Adjust this schema based on your actual data structure
whatsapp_schema = StructType([
    StructField("message_id", StringType(), True),
    StructField("conversation_id", StringType(), True),
    StructField("sender_id", StringType(), True),
    StructField("sender_name", StringType(), True),
    StructField("sender_phone", StringType(), True),
    StructField("recipient_id", StringType(), True),
    StructField("recipient_name", StringType(), True),
    StructField("recipient_phone", StringType(), True),
    StructField("message_text", StringType(), True),
    StructField("message_type", StringType(), True),
    StructField("timestamp", TimestampType(), True),
    StructField("status", StringType(), True),
    StructField("media_url", StringType(), True),
    StructField("media_type", StringType(), True),
    StructField("is_group_message", BooleanType(), True),
    StructField("group_id", StringType(), True),
    StructField("group_name", StringType(), True),
    StructField("quoted_message_id", StringType(), True),
    StructField("raw_data", StringType(), True)
])

# COMMAND ----------

# Function to check if source files exist
def check_source_exists(path):
    try:
        dbutils.fs.ls(path)
        return True
    except Exception as e:
        logger.error(f"Source path not found: {path}. Error: {str(e)}")
        return False

# COMMAND ----------

# Check if source exists
if not check_source_exists(SOURCE_PATH):
    logger.warning(f"Source path {SOURCE_PATH} does not exist. Creating empty Bronze table.")
    
    # Create empty DataFrame with schema
    empty_df = spark.createDataFrame([], whatsapp_schema)
    
    # Add ingestion metadata
    empty_df = empty_df \
        .withColumn("ingestion_timestamp", current_timestamp()) \
        .withColumn("source_file", lit("NO_SOURCE_FILE")) \
        .withColumn("processing_date", current_date())
    
    # Write as Delta table
    empty_df.write \
        .mode("overwrite") \
        .option("overwriteSchema", "true") \
        .format("delta") \
        .save(BRONZE_PATH)
    
    logger.info("Created empty Bronze table with schema")
    dbutils.notebook.exit("No source files found - created empty Bronze table")

# COMMAND ----------

# Read source data with explicit schema
try:
    # Check file format in source
    files = dbutils.fs.ls(SOURCE_PATH)
    
    if not files:
        raise Exception("No files found in source directory")
    
    # Determine file format from first file
    first_file = files[0].path
    
    if first_file.endswith(".parquet"):
        logger.info("Reading Parquet files")
        df = spark.read \
            .schema(whatsapp_schema) \
            .option("mergeSchema", "false") \
            .parquet(f"{SOURCE_PATH}/*.parquet")
            
    elif first_file.endswith(".json"):
        logger.info("Reading JSON files")
        df = spark.read \
            .schema(whatsapp_schema) \
            .option("multiLine", "true") \
            .json(f"{SOURCE_PATH}/*.json")
            
    elif first_file.endswith(".csv"):
        logger.info("Reading CSV files")
        df = spark.read \
            .schema(whatsapp_schema) \
            .option("header", "true") \
            .csv(f"{SOURCE_PATH}/*.csv")
    else:
        raise Exception(f"Unsupported file format: {first_file}")
        
    logger.info(f"Successfully read {df.count()} records from source")
    
except Exception as e:
    logger.error(f"Error reading source data: {str(e)}")
    
    # Try to read without schema as fallback
    try:
        logger.info("Attempting to read with schema inference...")
        df = spark.read \
            .option("inferSchema", "true") \
            .parquet(f"{SOURCE_PATH}/*.parquet")
        
        logger.warning("Schema inference succeeded. Actual schema:")
        df.printSchema()
        
    except Exception as e2:
        logger.error(f"Schema inference also failed: {str(e2)}")
        raise Exception(f"Cannot read source data: {str(e)} | {str(e2)}")

# COMMAND ----------

# Add ingestion metadata
df_with_metadata = df \
    .withColumn("ingestion_timestamp", current_timestamp()) \
    .withColumn("source_file", input_file_name()) \
    .withColumn("processing_date", current_date()) \
    .withColumn("row_hash", sha2(concat_ws("|", *[col(c) for c in df.columns]), 256))

# COMMAND ----------

# Write to Bronze layer
logger.info(f"Writing {df_with_metadata.count()} records to Bronze layer")

# Check if Delta table exists
if DeltaTable.isDeltaTable(spark, BRONZE_PATH):
    logger.info("Appending to existing Bronze table")
    df_with_metadata.write \
        .mode("append") \
        .format("delta") \
        .save(BRONZE_PATH)
else:
    logger.info("Creating new Bronze table")
    df_with_metadata.write \
        .mode("overwrite") \
        .option("overwriteSchema", "true") \
        .format("delta") \
        .save(BRONZE_PATH)

# COMMAND ----------

# Optimize and create table if not exists
spark.sql(f"""
    CREATE TABLE IF NOT EXISTS bronze.whatsapp_messages
    USING DELTA
    LOCATION '{BRONZE_PATH}'
""")

# Optimize table
spark.sql("OPTIMIZE bronze.whatsapp_messages")

# COMMAND ----------

# Data quality checks
total_records = spark.read.format("delta").load(BRONZE_PATH).count()
null_messages = spark.read.format("delta").load(BRONZE_PATH).filter(col("message_id").isNull()).count()
duplicates = spark.read.format("delta").load(BRONZE_PATH).groupBy("message_id").count().filter(col("count") > 1).count()

logger.info(f"Bronze ingestion completed:")
logger.info(f"- Total records: {total_records}")
logger.info(f"- Records with null message_id: {null_messages}")
logger.info(f"- Duplicate message_ids: {duplicates}")

# COMMAND ----------

# Return summary
result = {
    "status": "SUCCESS",
    "records_ingested": total_records,
    "null_records": null_messages,
    "duplicates": duplicates,
    "bronze_path": BRONZE_PATH,
    "timestamp": datetime.now().isoformat()
}

dbutils.notebook.exit(str(result))