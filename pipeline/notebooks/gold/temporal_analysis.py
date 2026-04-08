# Databricks notebook source
# MAGIC %md
# MAGIC # Gold: Temporal Analysis
# MAGIC Heatmap de conversao por hora x dia da semana. Horarios otimos de contato.

import logging
import time

from pyspark.sql import functions as F

logger = logging.getLogger("gold.temporal_analysis")
CATALOG = spark.conf.get("pipeline.catalog", "medallion")
start_time = time.time()

conversations = spark.table(f"{CATALOG}.silver.conversations_enriched")

# ============================================================
# 1. HEATMAP: HORA x DIA DA SEMANA x CONVERSAO
# ============================================================
temporal = (
    conversations.withColumn("contact_hour", F.hour("first_message_at"))
    .withColumn("contact_dow", F.dayofweek("first_message_at"))
    .withColumn("dow_name", F.date_format("first_message_at", "EEEE"))
    .groupBy("contact_hour", "contact_dow", "dow_name")
    .agg(
        F.count("*").alias("total_contacts"),
        F.sum(F.when(F.col("outcome") == "venda_fechada", 1).otherwise(0)).alias("wins"),
        F.avg("avg_response_time_sec").alias("avg_response_time"),
        F.avg("total_messages").alias("avg_messages"),
    )
    .withColumn("conversion_rate", F.round(F.col("wins") / F.col("total_contacts") * 100, 2))
    .orderBy("contact_dow", "contact_hour")
)

# ============================================================
# 2. MELHOR HORARIO POR DIA
# ============================================================
from pyspark.sql import Window

w = Window.partitionBy("contact_dow").orderBy(F.col("conversion_rate").desc())
best_hours = temporal.withColumn("rank", F.row_number().over(w)).filter(F.col("rank") == 1).drop(
    "rank"
)

# ============================================================
# 3. SALVAR
# ============================================================
GOLD_TABLE = f"{CATALOG}.gold.temporal_analysis"
temporal.write.format("delta").mode("overwrite").option("mergeSchema", "true").saveAsTable(
    GOLD_TABLE
)

duration = round(time.time() - start_time, 2)
logger.info(f"Gold temporal_analysis em {duration}s")
dbutils.notebook.exit(f"SUCCESS in {duration}s")
