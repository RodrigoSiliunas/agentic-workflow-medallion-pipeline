# Databricks notebook source
# MAGIC %md
# MAGIC # Gold: Competitor Intelligence
# MAGIC Concorrentes mencionados, price gap, loss rate por concorrente.

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
logger = logging.getLogger("gold.competitor_intel")
start_time = time.time()

leads = spark.table(f"{CATALOG}.silver.leads_profile")
conversations = spark.table(f"{CATALOG}.silver.conversations_enriched")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Explodir Concorrentes por Conversa

# COMMAND ----------

leads_with_outcome = leads.join(
    conversations.select("conversation_id", "outcome"), on="conversation_id"
)

competitors = leads_with_outcome.select(
    "conversation_id",
    "outcome",
    F.explode_outer("competitors_mentioned").alias("competitor"),
    "prices_mentioned",
).filter(F.col("competitor").isNotNull())

# COMMAND ----------

# MAGIC %md
# MAGIC ## Metricas por Concorrente

# COMMAND ----------

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

# COMMAND ----------

# MAGIC %md
# MAGIC ## Salvar

# COMMAND ----------

GOLD_TABLE = f"{CATALOG}.gold.competitor_intel"
comp_stats.write.format("delta").mode("overwrite").option("mergeSchema", "true").saveAsTable(
    GOLD_TABLE
)

lake.write_parquet(comp_stats, "gold/competitor_intel/")

duration = round(time.time() - start_time, 2)
logger.info(f"Gold competitor_intel: {comp_stats.count()} concorrentes em {duration}s")
dbutils.notebook.exit(f"SUCCESS in {duration}s")
