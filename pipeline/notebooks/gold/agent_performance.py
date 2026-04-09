# Databricks notebook source
# MAGIC %md
# MAGIC # Gold: Agent Performance
# MAGIC Scoring dos 20 agentes com percentis relativos, taxas de conversao/ghosting/perda,
# MAGIC e metricas de engajamento. Permite ranking comparativo entre agentes.
# MAGIC
# MAGIC **Camada:** Gold | **Dependencia:** silver.conversations_enriched
# MAGIC **Output:** `gold.agent_performance`
# MAGIC
# MAGIC _Ultima atualizacao: 2026-04-09_

# COMMAND ----------

# DBTITLE 1,Imports e Setup
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

# COMMAND ----------

# DBTITLE 1,Parametros
dbutils.widgets.text("catalog", "medallion", "Catalog Name")
dbutils.widgets.text("scope", "medallion-pipeline", "Secret Scope")

CATALOG = dbutils.widgets.get("catalog")
SCOPE = dbutils.widgets.get("scope")

# Inicializa lake client e logger
lake = S3Lake(dbutils, spark, scope=SCOPE)
logger = logging.getLogger("gold.agent_performance")
start_time = time.time()

# COMMAND ----------

# DBTITLE 1,Carregar Conversas Enriquecidas
conversations = spark.table(f"{CATALOG}.silver.conversations_enriched")

# COMMAND ----------

# DBTITLE 1,Metricas por Agente
# Calcula metricas brutas para cada agente: conversas, vendas, ghosting, perdas,
# media de mensagens, duracao e response time
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

# DBTITLE 1,Taxas de Conversao, Ghosting e Perda
# Calcula taxas percentuais para facilitar comparacao entre agentes
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

# DBTITLE 1,Percentis (ranking relativo entre agentes)
# Percentis permitem saber onde cada agente se posiciona em relacao aos demais
# Ex: win_rate_percentile=80 significa que o agente e melhor que 80% dos outros
agents = agents.withColumns(
    {
        "win_rate_percentile": F.round(
            F.percent_rank().over(Window.orderBy("win_rate")) * 100, 0
        ),
        # Response time invertido: menor tempo = melhor percentil
        "response_time_percentile": F.round(
            F.percent_rank().over(Window.orderBy(F.col("avg_response_time").desc())) * 100, 0
        ),
        # Ghosting invertido: menor taxa de ghosting = melhor
        "ghosting_rate_percentile": F.round(
            F.percent_rank().over(Window.orderBy("ghosting_rate")) * 100, 0
        ),
    }
)

# COMMAND ----------

# DBTITLE 1,Salvar no Unity Catalog e S3
GOLD_TABLE = f"{CATALOG}.gold.agent_performance"
agents.write.format("delta").mode("overwrite").option("mergeSchema", "true").saveAsTable(GOLD_TABLE)

# Backup em Parquet no S3
lake.write_parquet(agents, "gold/agent_performance/")

duration = round(time.time() - start_time, 2)
logger.info(f"Gold agent_performance: {agents.count()} agents em {duration}s")
dbutils.notebook.exit(f"SUCCESS: {agents.count()} agents scored in {duration}s")
