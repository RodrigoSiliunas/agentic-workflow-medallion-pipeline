# Databricks notebook source
# MAGIC %md
# MAGIC # Bronze Layer - Data Ingestion
# MAGIC Pipeline: seguradora-whatsapp

from pyspark.sql import SparkSession
from pyspark.sql.types import *
from pyspark.sql.functions import *
from delta.tables import DeltaTable
import logging
from datetime import datetime

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize Spark
spark = SparkSession.builder.appName("BronzeIngestion").getOrCreate()

# Configuration
SOURCE_PATH = "/mnt/landing/whatsapp/messages"  # Adjust based on your actual source
BRONZE_PATH = "/mnt/bronze/whatsapp_messages"
CHECKPOINT_PATH = "/mnt/checkpoints/bronze/whatsapp_messages"

# Define schema explicitly for WhatsApp messages
# Adjust this schema based on your actual data structure
whatsapp_schema = StructType([
    StructField("message_id", StringType(), True),
    StructField("conversation_id", StringType(), True),
    StructField("sender_phone", StringType(), True),
    StructField("recipient_phone", StringType(), True),
    StructField("message_text", StringType(), True),
    StructField("timestamp", TimestampType(), True),
    StructField("message_type", StringType(), True),
    StructField("status", StringType(), True),
    StructField("metadata", StringType(), True)
])

try:
    # Check if source path exists and has files
    try:
        files = dbutils.fs.ls(SOURCE_PATH)
        parquet_files = [f for f in files if f.path.endswith('.parquet')]
        logger.info(f"Found {len(parquet_files)} parquet files in {SOURCE_PATH}")
        
        if len(parquet_files) == 0:
            raise ValueError(f"No parquet files found in {SOURCE_PATH}")
            
    except Exception as e:
        logger.error(f"Error accessing source path {SOURCE_PATH}: {str(e)}")
        # Try alternative paths
        alt_paths = [
            "/mnt/raw/whatsapp",
            "/FileStore/whatsapp/messages",
            "/tmp/whatsapp/messages"
        ]
        for alt_path in alt_paths:
            try:
                files = dbutils.fs.ls(alt_path)
                if any(f.path.endswith('.parquet') for f in files):
                    SOURCE_PATH = alt_path
                    logger.info(f"Using alternative path: {SOURCE_PATH}")
                    break
            except:
                continue
        else:
            raise ValueError("No valid source path found with parquet files")
    
    # Method 1: Try Auto Loader first (recommended for streaming ingestion)
    logger.info("Attempting ingestion with Auto Loader...")
    try:
        df = (spark.readStream
              .format("cloudFiles")
              .option("cloudFiles.format", "parquet")
              .option("cloudFiles.inferColumnTypes", "true")
              .option("cloudFiles.schemaLocation", CHECKPOINT_PATH + "/schema")
              .option("cloudFiles.schemaEvolutionMode", "addNewColumns")
              .load(SOURCE_PATH))
        
        # Add ingestion metadata
        df_with_metadata = df.withColumn("_ingestion_timestamp", current_timestamp()) \
                             .withColumn("_source_file", input_file_name()) \
                             .withColumn("_processing_date", current_date())
        
        # Write to Bronze Delta table
        query = (df_with_metadata.writeStream
                 .format("delta")
                 .outputMode("append")
                 .option("checkpointLocation", CHECKPOINT_PATH)
                 .option("mergeSchema", "true")
                 .trigger(availableNow=True)
                 .toTable("bronze.whatsapp_messages"))
        
        query.awaitTermination()
        logger.info("Auto Loader ingestion completed successfully")
        
    except Exception as e:
        logger.warning(f"Auto Loader failed: {str(e)}. Trying batch read...")
        
        # Method 2: Fallback to batch read with explicit schema
        try:
            # First try to infer schema from a sample file
            sample_file = parquet_files[0].path
            try:
                inferred_df = spark.read.parquet(sample_file)
                actual_schema = inferred_df.schema
                logger.info(f"Successfully inferred schema from {sample_file}")
            except:
                # Use predefined schema if inference fails
                actual_schema = whatsapp_schema
                logger.info("Using predefined schema")
            
            # Read all parquet files with schema
            df = spark.read.schema(actual_schema).parquet(SOURCE_PATH)
            
            # Add ingestion metadata
            df_with_metadata = df.withColumn("_ingestion_timestamp", current_timestamp()) \
                                 .withColumn("_source_file", input_file_name()) \
                                 .withColumn("_processing_date", current_date())
            
            # Write to Bronze Delta table
            df_with_metadata.write \
                .mode("append") \
                .option("mergeSchema", "true") \
                .saveAsTable("bronze.whatsapp_messages")
            
            logger.info(f"Batch ingestion completed. Rows written: {df_with_metadata.count()}")
            
        except Exception as batch_error:
            logger.error(f"Batch read also failed: {str(batch_error)}")
            
            # Method 3: Last resort - read with permissive mode
            df = (spark.read
                  .option("mode", "PERMISSIVE")
                  .option("columnNameOfCorruptRecord", "_corrupt_record")
                  .parquet(SOURCE_PATH))
            
            # Add metadata and write
            df_with_metadata = df.withColumn("_ingestion_timestamp", current_timestamp()) \
                                 .withColumn("_source_file", input_file_name()) \
                                 .withColumn("_processing_date", current_date()) \
                                 .withColumn("_ingestion_mode", lit("permissive"))
            
            df_with_metadata.write \
                .mode("append") \
                .option("mergeSchema", "true") \
                .saveAsTable("bronze.whatsapp_messages")
            
            corrupt_count = df_with_metadata.filter(col("_corrupt_record").isNotNull()).count()
            if corrupt_count > 0:
                logger.warning(f"Found {corrupt_count} corrupt records")
    
    # Verify ingestion
    bronze_count = spark.table("bronze.whatsapp_messages").count()
    logger.info(f"Bronze table now contains {bronze_count} total records")
    
    # Display sample for verification
    display(spark.table("bronze.whatsapp_messages").limit(10))
    
except Exception as e:
    logger.error(f"Bronze ingestion failed: {str(e)}")
    raise

# COMMAND ----------

# MAGIC %md
# MAGIC ## Data Quality Checks

# Run basic quality checks
quality_df = spark.table("bronze.whatsapp_messages")

# Check for nulls in critical fields
null_checks = quality_df.agg(
    sum(when(col("message_id").isNull(), 1).otherwise(0)).alias("null_message_ids"),
    sum(when(col("timestamp").isNull(), 1).otherwise(0)).alias("null_timestamps")
).collect()[0]

logger.info(f"Data quality - Null message IDs: {null_checks['null_message_ids']}, Null timestamps: {null_checks['null_timestamps']}")

# COMMAND ----------

# Return success
dbutils.notebook.exit("Bronze ingestion completed successfully")