# Databricks notebook source
# MAGIC %md
# MAGIC # Bronze Layer - Data Ingestion
# MAGIC This notebook ingests raw data from source systems into the Bronze layer

from pyspark.sql import SparkSession
from pyspark.sql.functions import current_timestamp, input_file_name, col
from delta.tables import DeltaTable
import logging
from datetime import datetime

# COMMAND ----------

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# COMMAND ----------

# Configuration
# Note: Ensure these paths are accessible and credentials are properly configured
SOURCE_PATH = "s3a://your-source-bucket/raw-data/"  # Update with actual source
BRONZE_PATH = "s3a://your-target-bucket/bronze/"  # Update with actual target
CHECKPOINT_PATH = "s3a://your-target-bucket/checkpoints/bronze/"

# COMMAND ----------

# Configure S3 access (if not already configured at cluster level)
# Option 1: Using IAM role (recommended)
spark.conf.set("spark.hadoop.fs.s3a.aws.credentials.provider", "com.amazonaws.auth.InstanceProfileCredentialsProvider")

# Option 2: Using access keys (less secure, use only for testing)
# spark.conf.set("spark.hadoop.fs.s3a.access.key", dbutils.secrets.get(scope="aws", key="access_key"))
# spark.conf.set("spark.hadoop.fs.s3a.secret.key", dbutils.secrets.get(scope="aws", key="secret_key"))

# Additional S3 configurations
spark.conf.set("spark.hadoop.fs.s3a.impl", "org.apache.hadoop.fs.s3a.S3AFileSystem")
spark.conf.set("spark.hadoop.fs.s3a.fast.upload", "true")

# COMMAND ----------

def ingest_to_bronze(source_path, bronze_path, table_name):
    """
    Ingest data from source to bronze layer with metadata
    """
    try:
        logger.info(f"Starting ingestion for {table_name} from {source_path}")
        
        # Test S3 access first
        try:
            dbutils.fs.ls(source_path)
            logger.info(f"Successfully accessed source path: {source_path}")
        except Exception as e:
            logger.error(f"Cannot access source path {source_path}: {str(e)}")
            raise
            
        # Read source data
        df = spark.read \
            .option("multiLine", "true") \
            .option("inferSchema", "true") \
            .json(source_path)
        
        # Add ingestion metadata
        df_with_metadata = df \
            .withColumn("_ingestion_timestamp", current_timestamp()) \
            .withColumn("_source_file", input_file_name()) \
            .withColumn("_ingestion_date", current_timestamp().cast("date"))
        
        # Write to bronze layer
        bronze_table_path = f"{bronze_path}/{table_name}"
        
        # Check if table exists
        if DeltaTable.isDeltaTable(spark, bronze_table_path):
            logger.info(f"Appending to existing table: {bronze_table_path}")
            df_with_metadata.write \
                .mode("append") \
                .option("mergeSchema", "true") \
                .partitionBy("_ingestion_date") \
                .format("delta") \
                .save(bronze_table_path)
        else:
            logger.info(f"Creating new table: {bronze_table_path}")
            df_with_metadata.write \
                .mode("overwrite") \
                .option("overwriteSchema", "true") \
                .partitionBy("_ingestion_date") \
                .format("delta") \
                .save(bronze_table_path)
        
        # Optimize table
        spark.sql(f"OPTIMIZE delta.`{bronze_table_path}`")
        
        logger.info(f"Successfully ingested {df_with_metadata.count()} records to {table_name}")
        return True
        
    except Exception as e:
        logger.error(f"Failed to ingest {table_name}: {str(e)}")
        raise

# COMMAND ----------

# Main execution
if __name__ == "__main__":
    try:
        # Example: Ingest WhatsApp messages
        # Update these paths according to your actual data structure
        tables_to_ingest = [
            {"source": f"{SOURCE_PATH}/whatsapp_messages/", "table": "whatsapp_messages"},
            {"source": f"{SOURCE_PATH}/whatsapp_contacts/", "table": "whatsapp_contacts"},
            {"source": f"{SOURCE_PATH}/whatsapp_media/", "table": "whatsapp_media"}
        ]
        
        for table_config in tables_to_ingest:
            ingest_to_bronze(
                source_path=table_config["source"],
                bronze_path=BRONZE_PATH,
                table_name=table_config["table"]
            )
        
        logger.info("Bronze ingestion completed successfully")
        
    except Exception as e:
        logger.error(f"Bronze ingestion failed: {str(e)}")
        raise

# COMMAND ----------

# MAGIC %md
# MAGIC ## Troubleshooting S3 Access
# MAGIC 
# MAGIC If you're still getting AccessDeniedException, verify:
# MAGIC 1. IAM role/user has required S3 permissions:
# MAGIC    - s3:ListBucket
# MAGIC    - s3:GetObject
# MAGIC    - s3:PutObject
# MAGIC    - s3:DeleteObject (for Delta operations)
# MAGIC 2. Bucket policy allows access from your Databricks workspace
# MAGIC 3. Correct region configuration
# MAGIC 4. No conflicting bucket ACLs