# Databricks notebook source
# MAGIC %md
# MAGIC # Silver Layer - Deduplication and Cleaning
# MAGIC Remove duplicates and perform basic data cleaning

from pyspark.sql import functions as F
from pyspark.sql.window import Window
from delta.tables import DeltaTable
import logging

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# COMMAND ----------

# Configuration
BRONZE_TABLE = "medallion.bronze.conversations"
SILVER_TABLE = "medallion.silver.messages_clean"

# COMMAND ----------

def validate_access():
    """Validate access to required tables before processing"""
    try:
        # Test read access to bronze
        bronze_count = spark.table(BRONZE_TABLE).count()
        logger.info(f"Bronze table accessible. Row count: {bronze_count}")
        
        # Test if silver table exists
        if spark.catalog.tableExists(SILVER_TABLE):
            silver_count = spark.table(SILVER_TABLE).count()
            logger.info(f"Silver table exists. Row count: {silver_count}")
        else:
            logger.info("Silver table does not exist yet. Will be created.")
            
        return True
    except Exception as e:
        logger.error(f"Access validation failed: {str(e)}")
        raise

# COMMAND ----------

def deduplicate_messages():
    """Remove duplicate messages based on message_id, keeping the latest by ingestion timestamp"""
    try:
        logger.info("Starting deduplication process...")
        
        # Read bronze data
        bronze_df = spark.table(BRONZE_TABLE)
        
        # Define window for deduplication - partition by message_id, order by ingestion timestamp desc
        window_spec = Window.partitionBy("message_id").orderBy(F.col("_ingestion_timestamp").desc())
        
        # Add row number and keep only the latest record for each message_id
        dedup_df = bronze_df.withColumn("row_num", F.row_number().over(window_spec)) \
            .filter(F.col("row_num") == 1) \
            .drop("row_num")
        
        # Add data quality columns
        clean_df = dedup_df \
            .withColumn("sender_name_normalized", 
                       F.when(F.col("sender_name").isNotNull(), 
                              F.upper(F.trim(F.col("sender_name"))))
                       .otherwise(None)) \
            .withColumn("_dedup_timestamp", F.current_timestamp())
        
        # Parse metadata JSON if exists
        clean_df = clean_df \
            .withColumn("meta_device", 
                       F.when(F.col("metadata").isNotNull(),
                              F.get_json_object(F.col("metadata"), "$.device"))
                       .otherwise(None)) \
            .withColumn("meta_city",
                       F.when(F.col("metadata").isNotNull(),
                              F.get_json_object(F.col("metadata"), "$.location.city"))
                       .otherwise(None)) \
            .withColumn("meta_state",
                       F.when(F.col("metadata").isNotNull(),
                              F.get_json_object(F.col("metadata"), "$.location.state"))
                       .otherwise(None))
        
        # Log statistics
        original_count = bronze_df.count()
        dedup_count = clean_df.count()
        duplicates_removed = original_count - dedup_count
        
        logger.info(f"Original records: {original_count}")
        logger.info(f"After deduplication: {dedup_count}")
        logger.info(f"Duplicates removed: {duplicates_removed}")
        
        return clean_df
        
    except Exception as e:
        logger.error(f"Deduplication failed: {str(e)}")
        raise

# COMMAND ----------

def write_to_silver(df):
    """Write deduplicated data to silver table with merge logic"""
    try:
        logger.info(f"Writing to silver table: {SILVER_TABLE}")
        
        # Check if table exists
        if spark.catalog.tableExists(SILVER_TABLE):
            logger.info("Silver table exists. Performing merge...")
            
            # Merge with existing data
            silver_table = DeltaTable.forName(spark, SILVER_TABLE)
            
            silver_table.alias("target").merge(
                df.alias("source"),
                "target.message_id = source.message_id"
            ).whenMatchedUpdateAll(
            ).whenNotMatchedInsertAll(
            ).execute()
            
            logger.info("Merge completed successfully")
        else:
            logger.info("Creating new silver table...")
            
            # Create new table
            df.write \
                .mode("overwrite") \
                .option("overwriteSchema", "true") \
                .saveAsTable(SILVER_TABLE)
            
            logger.info("Silver table created successfully")
            
        # Optimize table
        spark.sql(f"OPTIMIZE {SILVER_TABLE}")
        
    except Exception as e:
        logger.error(f"Failed to write to silver: {str(e)}")
        raise

# COMMAND ----------

def main():
    """Main execution function"""
    try:
        # Validate access
        validate_access()
        
        # Perform deduplication
        clean_df = deduplicate_messages()
        
        # Write to silver
        write_to_silver(clean_df)
        
        # Final validation
        final_count = spark.table(SILVER_TABLE).count()
        logger.info(f"Silver table updated. Final row count: {final_count}")
        
        # Display sample
        display(spark.table(SILVER_TABLE).limit(10))
        
    except Exception as e:
        logger.error(f"Pipeline failed: {str(e)}")
        raise

# COMMAND ----------

# Execute pipeline
if __name__ == "__main__":
    main()