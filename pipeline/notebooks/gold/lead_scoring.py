# Databricks notebook source
# MAGIC %md
# MAGIC # Gold: Lead Scoring
# MAGIC Score 0-100 baseado em features da conversa + sentimento.

import logging
import time

from pyspark.sql import functions as F

logger = logging.getLogger("gold.lead_scoring")
CATALOG = spark.conf.get("pipeline.catalog", "medallion")
start_time = time.time()

conversations = spark.table(f"{CATALOG}.silver.conversations_enriched")
sentiment = spark.table(f"{CATALOG}.gold.sentiment")
leads = spark.table(f"{CATALOG}.silver.leads_profile")

# ============================================================
# 1. FEATURES PARA SCORING
# ============================================================
features = (
    conversations.join(sentiment.select("conversation_id", "sentiment_score"), on="conversation_id")
    .join(
        leads.select(
            "conversation_id",
            F.size("cpf_masked").alias("has_cpf"),
            F.size("email_masked").alias("has_email"),
            F.size("plate_masked").alias("has_plate"),
        ),
        on="conversation_id",
        how="left",
    )
)

# ============================================================
# 2. SCORING (heuristica ponderada, 0-100)
# ============================================================
# Cada feature contribui com pontos para o score
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

# Normalizar para 0-100
scored = scored.withColumn(
    "lead_score", F.least(F.greatest(F.col("raw_score"), F.lit(0)), F.lit(100)).cast("int")
).withColumn(
    "score_tier",
    F.when(F.col("lead_score") >= 70, "hot")
    .when(F.col("lead_score") >= 40, "warm")
    .otherwise("cold"),
)

# ============================================================
# 3. SALVAR
# ============================================================
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

duration = round(time.time() - start_time, 2)
count = result.count()
logger.info(f"Gold lead_scoring: {count} leads em {duration}s")
dbutils.notebook.exit(f"SUCCESS: {count} leads scored in {duration}s")
