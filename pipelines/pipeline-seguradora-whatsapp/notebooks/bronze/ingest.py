# Databricks notebook source
# MAGIC %md
# MAGIC # Bronze Layer - Data Ingestion
# MAGIC This notebook ingests raw data into the bronze layer

from pyspark.sql import SparkSession
from pyspark.sql.functions import current_timestamp, lit, col
from datetime import datetime
import logging
import sys

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# COMMAND ----------

# Configuration
BRONZE_PATH = dbutils.widgets.get("bronze_path") if dbutils.widgets.get("bronze_path") else "s3a://your-bucket/bronze"
SOURCE_PATH = dbutils.widgets.get("source_path") if dbutils.widgets.get("source_path") else "s3a://your-bucket/raw"
SOURCE_FORMAT = dbutils.widgets.get("source_format") if dbutils.widgets.get("source_format") else "json"

# COMMAND ----------

# Test S3 access before proceeding
def test_s3_access(path):
    """
    Test if we have proper access to S3 path
    """
    try:
        # Try to list the path
        dbutils.fs.ls(path)
        logger.info(f"Successfully accessed path: {path}")
        return True
    except Exception as e:
        logger.error(f"Failed to access path {path}: {str(e)}")
        if "Forbidden" in str(e) or "AccessDenied" in str(e):
            logger.error("This is a permissions issue. Please check:")
            logger.error("1. IAM role attached to Databricks cluster has s3:GetObject, s3:ListBucket permissions")
            logger.error("2. S3 bucket policy allows access from Databricks")
            logger.error("3. The path exists and is correctly specified")
        return False

# COMMAND ----------

# Validate access to required paths
if not test_s3_access(SOURCE_PATH.rsplit('/', 1)[0]):
    raise Exception(f"Cannot access source path: {SOURCE_PATH}. Please fix S3 permissions.")

if not test_s3_access(BRONZE_PATH.rsplit('/', 1)[0]):
    raise Exception(f"Cannot access bronze path: {BRONZE_PATH}. Please fix S3 permissions.")

# COMMAND ----------

def ingest_to_bronze():
    """
    Ingest raw data to bronze layer with error handling
    """
    try:
        logger.info(f"Starting ingestion from {SOURCE_PATH} to {BRONZE_PATH}")
        
        # Read source data based on format
        if SOURCE_FORMAT.lower() == "json":
            df = spark.read.option("multiLine", "true").json(SOURCE_PATH)
        elif SOURCE_FORMAT.lower() == "csv":
            df = spark.read.option("header", "true").option("inferSchema", "true").csv(SOURCE_PATH)
        elif SOURCE_FORMAT.lower() == "parquet":
            df = spark.read.parquet(SOURCE_PATH)
        else:
            raise ValueError(f"Unsupported source format: {SOURCE_FORMAT}")
        
        # Add metadata columns
        df_with_metadata = df \
            .withColumn("ingestion_timestamp", current_timestamp()) \
            .withColumn("source_file", lit(SOURCE_PATH)) \
            .withColumn("processing_date", lit(datetime.now().strftime("%Y-%m-%d")))
        
        # Write to bronze layer
        df_with_metadata.write \
            .mode("append") \
            .partitionBy("processing_date") \
            .parquet(BRONZE_PATH)
        
        record_count = df.count()
        logger.info(f"Successfully ingested {record_count} records to bronze layer")
        
        # Return metrics
        return {
            "status": "success",
            "records_processed": record_count,
            "target_path": BRONZE_PATH,
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Failed to ingest data: {str(e)}")
        
        # Provide specific guidance based on error type
        error_msg = str(e)
        if "AccessDeniedException" in error_msg or "Forbidden" in error_msg:
            logger.error("\n=== S3 PERMISSION ERROR ===")
            logger.error("Action required:")
            logger.error("1. Go to AWS IAM console")
            logger.error("2. Find the IAM role used by your Databricks cluster")
            logger.error("3. Attach a policy with these permissions:")
            logger.error("""{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Action": [
                "s3:GetObject",
                "s3:ListBucket",
                "s3:PutObject",
                "s3:HeadObject"
            ],
            "Resource": [
                "arn:aws:s3:::your-bucket/*",
                "arn:aws:s3:::your-bucket"
            ]
        }
    ]
}""")
            logger.error("4. Restart the Databricks cluster after updating IAM")
        
        raise e

# COMMAND ----------

# Execute ingestion
result = ingest_to_bronze()
print(f"Ingestion completed: {result}")

# COMMAND ----------

# Data quality checks
def validate_bronze_data():
    """
    Validate data was properly written to bronze
    """
    try:
        bronze_df = spark.read.parquet(BRONZE_PATH)
        
        # Basic validations
        row_count = bronze_df.count()
        if row_count == 0:
            raise ValueError("No data found in bronze layer")
        
        # Check for required metadata columns
        required_cols = ["ingestion_timestamp", "source_file", "processing_date"]
        missing_cols = [col for col in required_cols if col not in bronze_df.columns]
        if missing_cols:
            raise ValueError(f"Missing required columns: {missing_cols}")
        
        logger.info(f"Bronze validation passed. Total rows: {row_count}")
        return True
        
    except Exception as e:
        logger.error(f"Bronze validation failed: {str(e)}")
        return False

# COMMAND ----------

# Run validation
if validate_bronze_data():
    dbutils.notebook.exit("SUCCESS")
else:
    dbutils.notebook.exit("VALIDATION_FAILED")