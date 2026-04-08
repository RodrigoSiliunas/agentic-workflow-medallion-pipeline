# Databricks notebook source
# MAGIC %md
# MAGIC # Silver Task 2c: Conversation Enrichment
# MAGIC Metricas agregadas por conversa: total mensagens, duracao, response_time medio, etc.

import logging
import time

from pyspark.sql import functions as F

logger = logging.getLogger("silver.enrichment")

# ============================================================
# TASK VALUES
# ============================================================
try:
    should_process = dbutils.jobs.taskValues.get(
        taskKey="agent_pre", key="should_process", default=True
    )
    if not should_process:
        dbutils.notebook.exit("SKIP")
except Exception:
    pass

# ============================================================
# CONFIGURACAO
# ============================================================
CATALOG = spark.conf.get("pipeline.catalog", "medallion")
SILVER_MESSAGES = f"{CATALOG}.silver.messages_clean"
SILVER_CONVERSATIONS = f"{CATALOG}.silver.conversations_enriched"

start_time = time.time()

# ============================================================
# 1. LER MESSAGES_CLEAN
# ============================================================
df = spark.table(SILVER_MESSAGES)

# ============================================================
# 2. AGREGAR METRICAS POR CONVERSA
# ============================================================
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

# Duração da conversa em minutos
conversations = conversations.withColumn(
    "duration_minutes",
    (F.unix_timestamp("last_message_at") - F.unix_timestamp("first_message_at")) / 60,
)

# ============================================================
# 3. SALVAR
# ============================================================
(
    conversations.write.format("delta")
    .mode("overwrite")
    .option("mergeSchema", "true")
    .saveAsTable(SILVER_CONVERSATIONS)
)

conv_count = spark.table(SILVER_CONVERSATIONS).count()
duration = round(time.time() - start_time, 2)

logger.info(f"Silver conversations_enriched: {conv_count} conversas em {duration}s")

try:
    dbutils.jobs.taskValues.set(key="status", value="SUCCESS")
    dbutils.jobs.taskValues.set(key="rows_output", value=conv_count)
    dbutils.jobs.taskValues.set(key="duration_sec", value=duration)
except Exception:
    pass

dbutils.notebook.exit(f"SUCCESS: {conv_count} conversations enriched in {duration}s")
