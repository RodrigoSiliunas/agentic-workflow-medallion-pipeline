# Databricks notebook source
# MAGIC %md
# MAGIC # Gold: Lead Scoring
# MAGIC Score de 0-100 para cada lead baseado em features da conversa, sentimento,
# MAGIC dados fornecidos (CPF, email, placa), response time e engajamento.
# MAGIC Classifica leads em tiers: hot (>=70), warm (>=40), cold (<40).
# MAGIC
# MAGIC **Camada:** Gold | **Dependencia:** silver.conversations_enriched, gold.sentiment, silver.leads_profile
# MAGIC **Output:** `gold.lead_scoring`
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
_repo_root = "/".join(_nb_path.split("/")[:4])
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
logger = logging.getLogger("gold.lead_scoring")
start_time = time.time()

# COMMAND ----------

# DBTITLE 1,Carregar Tabelas de Dependencia
# Combina dados de 3 fontes para construir features de scoring
conversations = spark.table(f"{CATALOG}.silver.conversations_enriched")
sentiment = spark.table(f"{CATALOG}.gold.sentiment")
leads = spark.table(f"{CATALOG}.silver.leads_profile")

# COMMAND ----------

# DBTITLE 1,Montar Features para Scoring
# Join das 3 tabelas: conversas + sentimento + entidades fornecidas pelo lead
features = (
    conversations.join(sentiment.select("conversation_id", "sentiment_score"), on="conversation_id")
    .join(
        leads.select(
            "conversation_id",
            # Conta quantos dados sensiveis o lead forneceu (indica confianca)
            F.size("cpf_masked").alias("has_cpf"),
            F.size("email_masked").alias("has_email"),
            F.size("plate_masked").alias("has_plate"),
        ),
        on="conversation_id",
        how="left",
    )
)

# COMMAND ----------

# DBTITLE 1,Scoring Heuristico Ponderado (0-100)
# Formula de scoring com pesos por categoria:
# - Engajamento: ate 30 pts (3 pts por mensagem inbound, cap em 30)
# - Sentimento: ate 20 pts (normaliza -1/+1 para 0-20)
# - Dados fornecidos: ate 20 pts (CPF=8, email=6, placa=6)
# - Response time: ate 15 pts (rapido = mais pontos)
# - Horario comercial: ate 5 pts (bonus se respondeu em horario util)
# - Conversa longa: ate 10 pts (bonus para conversas com muitas mensagens)
scored = features.withColumn(
    "raw_score",
    (
        # Engajamento (max 30 pts)
        F.least(F.col("inbound_count") * 3, F.lit(30))
        # Sentimento (max 20 pts)
        + F.round((F.col("sentiment_score") + 1) * 10, 0)
        # Dados fornecidos (max 20 pts)
        + F.when(F.col("has_cpf") > 0, 8).otherwise(0)
        + F.when(F.col("has_email") > 0, 6).otherwise(0)
        + F.when(F.col("has_plate") > 0, 6).otherwise(0)
        # Response time rapido (max 15 pts)
        + F.when(F.col("avg_response_time_sec") < 60, 15)
        .when(F.col("avg_response_time_sec") < 180, 10)
        .when(F.col("avg_response_time_sec") < 600, 5)
        .otherwise(0)
        # Horario comercial (max 5 pts)
        + F.when(F.col("business_hours_messages") > 0, 5).otherwise(0)
        # Bonus: conversa longa (max 10 pts)
        + F.when(F.col("total_messages") > 15, 10)
        .when(F.col("total_messages") > 8, 5)
        .otherwise(0)
    ),
)

# Clamp no range 0-100 e classifica em tiers
scored = scored.withColumn(
    "lead_score", F.least(F.greatest(F.col("raw_score"), F.lit(0)), F.lit(100)).cast("int")
).withColumn(
    "score_tier",
    F.when(F.col("lead_score") >= 70, "hot")
    .when(F.col("lead_score") >= 40, "warm")
    .otherwise("cold"),
)

# COMMAND ----------

# DBTITLE 1,Salvar no Unity Catalog e S3
# Seleciona apenas colunas relevantes para a tabela final
result = scored.select(
    "conversation_id",
    "outcome",
    "lead_score",
    "score_tier",
    "raw_score",
    "inbound_count",
    "sentiment_score",
    "avg_response_time_sec",
    "total_messages",
    "campaign_id",
    "agent_id",
)

GOLD_TABLE = f"{CATALOG}.gold.lead_scoring"
result.write.format("delta").mode("overwrite").option("mergeSchema", "true").saveAsTable(GOLD_TABLE)

# Backup em Parquet no S3
lake.write_parquet(result, "gold/lead_scoring/")

duration = round(time.time() - start_time, 2)
count = result.count()
logger.info(f"Gold lead_scoring: {count} leads em {duration}s")
dbutils.notebook.exit(f"SUCCESS: {count} leads scored in {duration}s")
