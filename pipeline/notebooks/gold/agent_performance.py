# Databricks notebook source
# MAGIC %md
# MAGIC # Gold: Agent Performance
# MAGIC Scoring com percentis entre os 20 agentes, recomendacoes automatizadas.

# COMMAND ----------

import logging
import sys
import time

from pyspark.sql import functions as F

logger = logging.getLogger("gold.agent_performance")

sys.path.insert(0, "/Workspace/Repos/rodrigosiliunas1@gmail.com/agentic-workflow-medallion-pipeline/pipeline")
from pipeline_lib.storage import S3Lake

lake = S3Lake(dbutils)
CATALOG = "medallion"
start_time = time.time()

conversations = spark.table(f"{CATALOG}.silver.conversations_enriched")

# COMMAND ----------

# ============================================================
# 1. METRICAS POR AGENTE
# ============================================================
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

# ============================================================
# 2. TAXAS E SCORES
# ============================================================
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

# ============================================================
# 3. PERCENTIS (ranking relativo)
# ============================================================
agents = agents.withColumns(
    {
        "win_rate_percentile": F.round(
            F.percent_rank().over(F.Window.orderBy("win_rate")) * 100, 0
        ),
        "response_time_percentile": F.round(
            F.percent_rank().over(F.Window.orderBy(F.col("avg_response_time").desc())) * 100, 0
        ),
        "ghosting_rate_percentile": F.round(
            F.percent_rank().over(F.Window.orderBy("ghosting_rate")) * 100, 0
        ),
    }
)

# COMMAND ----------

# ============================================================
# 4. SALVAR
# ============================================================
GOLD_TABLE = f"{CATALOG}.gold.agent_performance"
agents.write.format("delta").mode("overwrite").option("mergeSchema", "true").saveAsTable(GOLD_TABLE)

# Upload para S3
tmp = lake.make_temp_dir("gold_agent_perf_")
local_path = f"{tmp}/agent_performance"
agents.write.format("delta").mode("overwrite").option("mergeSchema", "true").save(local_path)
lake.upload_dir(local_path, "gold/agent_performance/")

duration = round(time.time() - start_time, 2)
logger.info(f"Gold agent_performance: {agents.count()} agents em {duration}s")
dbutils.notebook.exit(f"SUCCESS: {agents.count()} agents scored in {duration}s")
