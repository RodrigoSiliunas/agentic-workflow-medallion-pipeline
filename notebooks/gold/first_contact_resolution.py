# Databricks notebook source
# MAGIC %md
# MAGIC # Gold: First Contact Resolution
# MAGIC % vendas fechadas na primeira conversa vs multiplos contatos.

import logging
import time

from pyspark.sql import Window
from pyspark.sql import functions as F

logger = logging.getLogger("gold.first_contact_resolution")
CATALOG = spark.conf.get("pipeline.catalog", "medallion")
start_time = time.time()

leads = spark.table(f"{CATALOG}.silver.leads_profile")
conversations = spark.table(f"{CATALOG}.silver.conversations_enriched")

# ============================================================
# 1. IDENTIFICAR MESMO LEAD EM CONVERSAS DIFERENTES (via phone_masked hash)
# ============================================================
# Usar lead_phone hasheado para agrupar conversas do mesmo lead
leads_with_conv = leads.join(
    conversations.select("conversation_id", "outcome", "first_message_at"),
    on="conversation_id",
)

# Contar conversas por lead (usando lead_phone como identificador)
lead_contacts = leads_with_conv.select(
    "conversation_id", "lead_phone", "outcome", "first_message_at"
)

w = Window.partitionBy("lead_phone").orderBy("first_message_at")
lead_contacts = lead_contacts.withColumn(
    "contact_number", F.row_number().over(w)
).withColumn(
    "total_contacts", F.count("*").over(Window.partitionBy("lead_phone"))
)

# ============================================================
# 2. FIRST CONTACT RESOLUTION
# ============================================================
fcr = lead_contacts.withColumn(
    "is_first_contact_win",
    (F.col("contact_number") == 1) & (F.col("outcome") == "venda_fechada"),
)

fcr_summary = lead_contacts.groupBy("lead_phone").agg(
    F.count("*").alias("total_conversations"),
    F.sum(F.when(F.col("outcome") == "venda_fechada", 1).otherwise(0)).alias("total_wins"),
    F.min("contact_number").alias("first_win_contact"),
)

fcr_stats = fcr_summary.withColumn(
    "resolution_type",
    F.when(
        (F.col("total_wins") > 0) & (F.col("total_conversations") == 1),
        "first_contact_resolution",
    )
    .when(
        (F.col("total_wins") > 0) & (F.col("total_conversations") > 1),
        "multi_contact_resolution",
    )
    .when(F.col("total_wins") == 0, "no_resolution")
    .otherwise("unknown"),
)

# ============================================================
# 3. METRICAS AGREGADAS
# ============================================================
overall = fcr_stats.groupBy("resolution_type").agg(
    F.count("*").alias("leads"),
    F.avg("total_conversations").alias("avg_contacts"),
)

total_leads = fcr_stats.count()
overall = overall.withColumn(
    "pct_of_total", F.round(F.col("leads") / F.lit(total_leads) * 100, 2)
)

# ============================================================
# 4. SALVAR
# ============================================================
fcr_stats.write.format("delta").mode("overwrite").option("mergeSchema", "true").saveAsTable(
    f"{CATALOG}.gold.first_contact_resolution"
)

overall.write.format("delta").mode("overwrite").saveAsTable(
    f"{CATALOG}.gold.fcr_summary"
)

duration = round(time.time() - start_time, 2)
logger.info(f"Gold first_contact_resolution em {duration}s")
dbutils.notebook.exit(f"SUCCESS in {duration}s")
