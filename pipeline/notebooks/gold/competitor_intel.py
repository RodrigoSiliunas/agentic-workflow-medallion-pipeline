# Databricks notebook source
# MAGIC %md
# MAGIC # Gold: Competitor Intelligence
# MAGIC Concorrentes mencionados, price gap, loss rate por concorrente.

import logging
import sys
import time

from pyspark.sql import functions as F

logger = logging.getLogger("gold.competitor_intel")

sys.path.insert(0, "/Workspace/Repos/rodrigosiliunas1@gmail.com/agentic-workflow-medallion-pipeline/pipeline")
from pipeline_lib.storage import S3Lake

lake = S3Lake(dbutils)
CATALOG = spark.conf.get("pipeline.catalog", "medallion")
start_time = time.time()

leads = spark.table(f"{CATALOG}.silver.leads_profile")
conversations = spark.table(f"{CATALOG}.silver.conversations_enriched")

# ============================================================
# 1. EXPLODIR CONCORRENTES POR CONVERSA
# ============================================================
leads_with_outcome = leads.join(
    conversations.select("conversation_id", "outcome"), on="conversation_id"
)

competitors = leads_with_outcome.select(
    "conversation_id",
    "outcome",
    F.explode_outer("competitors_mentioned").alias("competitor"),
    "prices_mentioned",
).filter(F.col("competitor").isNotNull())

# ============================================================
# 2. METRICAS POR CONCORRENTE
# ============================================================
comp_stats = competitors.groupBy("competitor").agg(
    F.count("*").alias("mention_count"),
    F.sum(
        F.when(F.col("outcome").isin("perdido_concorrente", "perdido_preco"), 1).otherwise(0)
    ).alias("losses_when_mentioned"),
    F.sum(F.when(F.col("outcome") == "venda_fechada", 1).otherwise(0)).alias(
        "wins_despite_mention"
    ),
    F.avg(F.col("prices_mentioned").getItem(0)).alias("avg_competitor_price_mentioned"),
)

comp_stats = comp_stats.withColumns(
    {
        "loss_rate": F.round(
            F.col("losses_when_mentioned") / F.col("mention_count") * 100, 2
        ),
        "win_despite_rate": F.round(
            F.col("wins_despite_mention") / F.col("mention_count") * 100, 2
        ),
    }
).orderBy(F.col("mention_count").desc())

# ============================================================
# 3. SALVAR
# ============================================================
GOLD_TABLE = f"{CATALOG}.gold.competitor_intel"
comp_stats.write.format("delta").mode("overwrite").option("mergeSchema", "true").saveAsTable(
    GOLD_TABLE
)

# Upload para S3
tmp = lake.make_temp_dir("gold_competitor_")
local_path = f"{tmp}/competitor_intel"
comp_stats.write.format("delta").mode("overwrite").option("mergeSchema", "true").save(local_path)
lake.upload_dir(local_path, "gold/competitor_intel/")

duration = round(time.time() - start_time, 2)
logger.info(f"Gold competitor_intel: {comp_stats.count()} concorrentes em {duration}s")
dbutils.notebook.exit(f"SUCCESS in {duration}s")
