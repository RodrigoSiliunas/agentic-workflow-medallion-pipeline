# Databricks notebook source
# MAGIC %md
# MAGIC # Gold: Agent Performance
# MAGIC Scoring com percentis entre os 20 agentes, recomendacoes automatizadas.

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

from pyspark.sql import Window
from pyspark.sql import functions as F

# Auto-detect repo path from this notebook's location
_nb_path = dbutils.notebook.entry_point.getDbutils().notebook().getContext().notebookPath().get()
_repo_root = "/".join(_nb_path.split("/")[:5])
PIPELINE_ROOT = f"/Workspace{_repo_root}/pipeline"
sys.path.insert(0, PIPELINE_ROOT)

from pipeline_lib.storage import S3Lake

lake = S3Lake(dbutils, spark, scope=SCOPE)
logger = logging.getLogger("gold.agent_performance")
start_time = time.time()

conversations = spark.table(f"{CATALOG}.silver.conversations_enriched")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Metricas por Agente

# COMMAND ----------

agents = conversations.groupBy("agent_id").agg(
    F.count("*").alias("total_conversations"),
    F.sum(F.when(F.col("outcome") == "venda_fechada", 1).otherwise(0)).alias("wins"),
    F.sum(F.when(F.col("outcome") == "ghosting", 1).otherwise(0)).alias("ghosting_count"),
    F.sum(
        F.when(F.col("outcome").isin("perdido_preco", "perdido_concorrente"), 1).otherwise(0)
    ).alias("lost_count"),
    F.avg("total_messages").alias("avg_messages_per_conv"),
    F.avg("duration_minutes").alias("avg_duration_min"),
    F.avg("avg_response_time_sec").alias("avg_response_time"),
    F.avg("inbound_count").alias("avg_lead_engagement"),
)

# COMMAND ----------

# MAGIC %md
# MAGIC ## Taxas e Scores

# COMMAND ----------

agents = agents.withColumns(
    {
        "win_rate": F.round(F.col("wins") / F.col("total_conversations") * 100, 2),
        "ghosting_rate": F.round(
            F.col("ghosting_count") / F.col("total_conversations") * 100, 2
        ),
        "loss_rate": F.round(F.col("lost_count") / F.col("total_conversations") * 100, 2),
    }
)

# COMMAND ----------

# MAGIC %md
# MAGIC ## Percentis (ranking relativo)

# COMMAND ----------

agents = agents.withColumns(
    {
        "win_rate_percentile": F.round(
            F.percent_rank().over(Window.orderBy("win_rate")) * 100, 0
        ),
        "response_time_percentile": F.round(
            F.percent_rank().over(Window.orderBy(F.col("avg_response_time").desc())) * 100, 0
        ),
        "ghosting_rate_percentile": F.round(
            F.percent_rank().over(Window.orderBy("ghosting_rate")) * 100, 0
        ),
    }
)

# COMMAND ----------

# MAGIC %md
# MAGIC ## Salvar

# COMMAND ----------

GOLD_TABLE = f"{CATALOG}.gold.agent_performance"
agents.write.format("delta").mode("overwrite").option("mergeSchema", "true").saveAsTable(GOLD_TABLE)

lake.write_parquet(agents, "gold/agent_performance/")

duration = round(time.time() - start_time, 2)
logger.info(f"Gold agent_performance: {agents.count()} agents em {duration}s")
dbutils.notebook.exit(f"SUCCESS: {agents.count()} agents scored in {duration}s")
