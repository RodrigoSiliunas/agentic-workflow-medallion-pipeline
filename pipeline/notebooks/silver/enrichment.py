# Databricks notebook source
# MAGIC %md
# MAGIC # Silver Task 2c: Conversation Enrichment
# MAGIC Metricas agregadas por conversa: total mensagens, duracao, response_time medio, etc.

# COMMAND ----------

dbutils.widgets.text("catalog", "medallion", "Catalog Name")
dbutils.widgets.text("scope", "medallion-pipeline", "Secret Scope")

CATALOG = dbutils.widgets.get("catalog")
SCOPE = dbutils.widgets.get("scope")

# COMMAND ----------

import logging
import os
import sys
import time

from pyspark.sql import functions as F

# Auto-detect repo path from this notebook's location
_nb_path = dbutils.notebook.entry_point.getDbutils().notebook().getContext().notebookPath().get()
_repo_root = "/".join(_nb_path.split("/")[:5])
PIPELINE_ROOT = f"/Workspace{_repo_root}/pipeline"
sys.path.insert(0, PIPELINE_ROOT)

from pipeline_lib.storage import S3Lake

lake = S3Lake(dbutils, spark, scope=SCOPE)
logger = logging.getLogger("silver.enrichment")

# COMMAND ----------

try:
    should_process = dbutils.jobs.taskValues.get(
        taskKey="agent_pre", key="should_process", default=True
    )
    if not should_process:
        dbutils.notebook.exit("SKIP")
except Exception:
    pass

# COMMAND ----------

SILVER_MESSAGES = f"{CATALOG}.silver.messages_clean"
SILVER_CONVERSATIONS = f"{CATALOG}.silver.conversations_enriched"

start_time = time.time()

# COMMAND ----------

# MAGIC %md
# MAGIC ## Ler Messages Clean

# COMMAND ----------

df = spark.table(SILVER_MESSAGES)

# COMMAND ----------

# MAGIC %md
# MAGIC ## Agregar Metricas por Conversa

# COMMAND ----------

conversations = df.groupBy("conversation_id").agg(
    F.count("*").alias("total_messages"),
    F.sum(F.when(F.col("direction") == "inbound", 1).otherwise(0)).alias("inbound_count"),
    F.sum(F.when(F.col("direction") == "outbound", 1).otherwise(0)).alias("outbound_count"),
    F.min("timestamp").alias("first_message_at"),
    F.max("timestamp").alias("last_message_at"),
    F.first("conversation_outcome").alias("outcome"),
    F.first("campaign_id").alias("campaign_id"),
    F.first("agent_id").alias("agent_id"),
    F.first("meta_city").alias("city"),
    F.first("meta_state").alias("state"),
    F.first("meta_device").alias("device"),
    F.first("meta_lead_source").alias("lead_source"),
    F.avg("meta_response_time_sec").alias("avg_response_time_sec"),
    F.sum(
        F.when(F.col("meta_is_business_hours") == True, 1).otherwise(0)  # noqa: E712
    ).alias("business_hours_messages"),
    F.collect_set("message_type").alias("message_types_used"),
)

conversations = conversations.withColumn(
    "duration_minutes",
    (F.unix_timestamp("last_message_at") - F.unix_timestamp("first_message_at")) / 60,
)

# COMMAND ----------

# MAGIC %md
# MAGIC ## Salvar (UC + S3)

# COMMAND ----------

(
    conversations.write.format("delta")
    .mode("overwrite")
    .option("mergeSchema", "true")
    .saveAsTable(SILVER_CONVERSATIONS)
)

conv_count = spark.table(SILVER_CONVERSATIONS).count()

lake.write_parquet(conversations, "silver/conversations_enriched/")
logger.info("Parquet uploaded para S3 silver/conversations_enriched/")

duration = round(time.time() - start_time, 2)
logger.info(f"Silver conversations_enriched: {conv_count} conversas em {duration}s")

try:
    dbutils.jobs.taskValues.set(key="status", value="SUCCESS")
    dbutils.jobs.taskValues.set(key="rows_output", value=conv_count)
    dbutils.jobs.taskValues.set(key="duration_sec", value=duration)
except Exception:
    pass

dbutils.notebook.exit(f"SUCCESS: {conv_count} conversations enriched in {duration}s")
