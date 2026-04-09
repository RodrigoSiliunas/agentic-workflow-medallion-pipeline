# Databricks notebook source
# MAGIC %md
# MAGIC # Bronze Layer - Data Ingestion
# MAGIC Ingest raw data from source to Bronze layer with schema validation

from pyspark.sql import SparkSession
from pyspark.sql.functions import col, current_timestamp, lit
from pyspark.sql.types import StructType, StructField, StringType
import logging
from datetime import datetime

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize Spark session
spark = SparkSession.builder.appName("BronzeIngestion").getOrCreate()

# Define the expected schema for bronze.conversations
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

# Get expected column names
expected_columns = [field.name for field in expected_schema.fields]

def validate_and_clean_schema(df, expected_cols):
    """
    Validate DataFrame schema and remove unexpected columns
    """
    # Get current columns
    current_columns = df.columns
    
    # Log schema differences
    unexpected_cols = set(current_columns) - set(expected_cols)
    missing_cols = set(expected_cols) - set(current_columns)
    
    if unexpected_cols:
        logger.warning(f"Found unexpected columns that will be removed: {unexpected_cols}")
        # Remove unexpected columns
        df = df.select(*[col for col in current_columns if col in expected_cols])
    
    if missing_cols:
        logger.error(f"Missing required columns: {missing_cols}")
        raise ValueError(f"Schema validation failed: missing columns {missing_cols}")
    
    # Ensure column order matches expected schema
    df = df.select(*expected_cols)
    
    return df

try:
    # Read source data - adjust path based on your source
    # This could be from S3, ADLS, or mounted location
    source_path = "/mnt/landing/conversations/"
    
    logger.info(f"Starting bronze ingestion from {source_path}")
    
    # Read raw data
    raw_df = spark.read \
        .option("multiLine", "true") \
        .option("inferSchema", "false") \
        .json(source_path)
    
    logger.info(f"Read {raw_df.count()} records from source")
    logger.info(f"Source schema columns: {raw_df.columns}")
    
    # Validate and clean schema
    clean_df = validate_and_clean_schema(raw_df, expected_columns)
    
    # Add ingestion metadata
    bronze_df = clean_df \
        .withColumn("_ingestion_timestamp", current_timestamp()) \
        .withColumn("_source_file", lit(source_path))
    
    # Write to Bronze table
    bronze_table = "medallion.bronze.conversations"
    
    bronze_df.write \
        .mode("append") \
        .option("mergeSchema", "false") \
        .saveAsTable(bronze_table)
    
    # Log success metrics
    final_count = spark.read.table(bronze_table).count()
    logger.info(f"Successfully ingested data to {bronze_table}")
    logger.info(f"Total records in bronze table: {final_count}")
    
    # Display sample for verification
    display(bronze_df.limit(10))
    
except Exception as e:
    logger.error(f"Bronze ingestion failed: {str(e)}")
    # Log detailed error for debugging
    if 'raw_df' in locals():
        logger.error(f"Raw data schema: {raw_df.schema}")
        logger.error(f"Raw data columns: {raw_df.columns}")
    raise

# Return success
dbutils.notebook.exit("SUCCESS")