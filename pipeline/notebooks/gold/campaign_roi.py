# Databricks notebook source
# MAGIC %md
# MAGIC # Gold: Campaign ROI
# MAGIC Eficacia das 10 campanhas de marketing: conversion rate, lead quality (via scoring),
# MAGIC distribuicao de tiers hot/warm/cold, e analise geografica por estado.
# MAGIC
# MAGIC **Camada:** Gold | **Dependencia:** silver.conversations_enriched, gold.lead_scoring
# MAGIC **Output:** `gold.campaign_roi`, `gold.campaign_geo`
# MAGIC
# MAGIC _Ultima atualizacao: 2026-04-09_

# COMMAND ----------

# DBTITLE 1,Imports e Setup
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

# COMMAND ----------

# DBTITLE 1,Parametros
dbutils.widgets.text("catalog", "medallion", "Catalog Name")
dbutils.widgets.text("scope", "medallion-pipeline", "Secret Scope")

CATALOG = dbutils.widgets.get("catalog")
SCOPE = dbutils.widgets.get("scope")

# Inicializa lake client e logger
lake = S3Lake(dbutils, spark, scope=SCOPE)
logger = logging.getLogger("gold.campaign_roi")
start_time = time.time()

# COMMAND ----------

# DBTITLE 1,Carregar Tabelas de Dependencia
conversations = spark.table(f"{CATALOG}.silver.conversations_enriched")
lead_scores = spark.table(f"{CATALOG}.gold.lead_scoring")

# COMMAND ----------

# DBTITLE 1,Metricas por Campanha
# Junta conversas com lead scores para analisar qualidade dos leads por campanha
campaigns = conversations.join(
    lead_scores.select("conversation_id", "lead_score", "score_tier"), on="conversation_id"
)

# Calcula metricas agregadas por campanha: conversoes, ghosting, qualidade, performance
campaign_stats = campaigns.groupBy("campaign_id").agg(
    F.count("*").alias("total_leads"),
    F.sum(F.when(F.col("outcome") == "venda_fechada", 1).otherwise(0)).alias("conversions"),
    F.sum(F.when(F.col("outcome") == "ghosting", 1).otherwise(0)).alias("ghosting_count"),
    F.avg("lead_score").alias("avg_lead_quality"),
    F.avg("total_messages").alias("avg_messages_to_convert"),
    F.avg("duration_minutes").alias("avg_duration_min"),
    F.avg("avg_response_time_sec").alias("avg_response_time"),
    # Distribuicao de tiers por campanha
    F.sum(F.when(F.col("score_tier") == "hot", 1).otherwise(0)).alias("hot_leads"),
    F.sum(F.when(F.col("score_tier") == "warm", 1).otherwise(0)).alias("warm_leads"),
    F.sum(F.when(F.col("score_tier") == "cold", 1).otherwise(0)).alias("cold_leads"),
)

# Taxas percentuais de conversao e ghosting
campaign_stats = campaign_stats.withColumns(
    {
        "conversion_rate": F.round(F.col("conversions") / F.col("total_leads") * 100, 2),
        "ghosting_rate": F.round(F.col("ghosting_count") / F.col("total_leads") * 100, 2),
    }
).orderBy(F.col("conversion_rate").desc())

# COMMAND ----------

# DBTITLE 1,Analise Geografica por Campanha
# Cruza campanha x estado para identificar regioes com melhor conversao por campanha
geo_campaign = (
    conversations.groupBy("campaign_id", "state")
    .agg(
        F.count("*").alias("leads"),
        F.sum(F.when(F.col("outcome") == "venda_fechada", 1).otherwise(0)).alias("conversions"),
    )
    .withColumn("conversion_rate", F.round(F.col("conversions") / F.col("leads") * 100, 2))
)

# COMMAND ----------

# DBTITLE 1,Salvar no Unity Catalog e S3
GOLD_TABLE = f"{CATALOG}.gold.campaign_roi"
campaign_stats.write.format("delta").mode("overwrite").option("mergeSchema", "true").saveAsTable(
    GOLD_TABLE
)

# Salva analise geografica como tabela separada
geo_campaign.write.format("delta").mode("overwrite").saveAsTable(
    f"{CATALOG}.gold.campaign_geo"
)

# Backup em Parquet no S3
lake.write_parquet(campaign_stats, "gold/campaign_roi/")
lake.write_parquet(geo_campaign, "gold/campaign_geo/")

duration = round(time.time() - start_time, 2)
logger.info(f"Gold campaign_roi em {duration}s")
dbutils.notebook.exit(f"SUCCESS in {duration}s")
