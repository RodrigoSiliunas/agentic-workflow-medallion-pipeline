# Databricks notebook source
# MAGIC %md
# MAGIC # Gold: Persona Segmentation
# MAGIC Classificacao em 6 personas baseadas em comportamento.

import logging
import sys
import time

from pyspark.sql import functions as F

logger = logging.getLogger("gold.segmentation")

sys.path.insert(0, "/Workspace/Repos/rodrigosiliunas1@gmail.com/agentic-workflow-medallion-pipeline/pipeline")
from pipeline_lib.storage import S3Lake

lake = S3Lake(dbutils)
CATALOG = spark.conf.get("pipeline.catalog", "medallion")
start_time = time.time()

conversations = spark.table(f"{CATALOG}.silver.conversations_enriched")
sentiment = spark.table(f"{CATALOG}.gold.sentiment")
lead_scores = spark.table(f"{CATALOG}.gold.lead_scoring")
leads = spark.table(f"{CATALOG}.silver.leads_profile")

# ============================================================
# 1. COMBINAR FEATURES
# ============================================================
combined = (
    conversations.join(sentiment.select("conversation_id", "sentiment_score"), on="conversation_id")
    .join(lead_scores.select("conversation_id", "lead_score"), on="conversation_id")
    .join(
        leads.select(
            "conversation_id",
            F.size("cpf_masked").alias("provided_cpf"),
            F.size("email_masked").alias("provided_email"),
            F.size("plate_masked").alias("provided_plate"),
            F.size("competitors_mentioned").alias("mentioned_competitors"),
        ),
        on="conversation_id",
        how="left",
    )
)

# ============================================================
# 2. CLASSIFICACAO EM PERSONAS
# ============================================================
personas = combined.withColumn(
    "persona",
    F.when(
        (F.col("total_messages") <= 5) & (F.col("outcome") == "venda_fechada"),
        "decidido_rapido",
    )
    .when(
        (F.col("mentioned_competitors") > 0)
        & F.col("outcome").isin("perdido_preco", "perdido_concorrente"),
        "comparador_preco",
    )
    .when(
        (F.col("total_messages") >= 15)
        & F.col("outcome").isin("em_negociacao", "proposta_enviada"),
        "engajado_indeciso",
    )
    .when(
        (F.col("inbound_count") <= 3) & (F.col("outcome") == "ghosting"),
        "ghost",
    )
    .when(
        (F.col("provided_cpf") > 0) & (F.col("sentiment_score") > 0),
        "lead_quente",
    )
    .when(
        (F.col("outcome") == "desistencia_lead"),
        "curioso",
    )
    .otherwise("indefinido"),
)

# ============================================================
# 3. RESUMO POR PERSONA
# ============================================================
persona_summary = personas.groupBy("persona").agg(
    F.count("*").alias("total"),
    F.avg("lead_score").alias("avg_lead_score"),
    F.avg("sentiment_score").alias("avg_sentiment"),
    F.avg("total_messages").alias("avg_messages"),
    F.avg("avg_response_time_sec").alias("avg_response_time"),
)

# ============================================================
# 4. SALVAR
# ============================================================
# Tabela detalhada (por conversa)
personas_result = personas.select(
    "conversation_id", "persona", "outcome", "lead_score", "sentiment_score",
    "total_messages", "campaign_id", "agent_id",
)
personas_result.write.format("delta").mode("overwrite").option("mergeSchema", "true").saveAsTable(
    f"{CATALOG}.gold.personas"
)

# Tabela resumo
persona_summary.write.format("delta").mode("overwrite").saveAsTable(
    f"{CATALOG}.gold.persona_summary"
)

# Upload para S3
tmp1 = lake.make_temp_dir("gold_personas_")
local1 = f"{tmp1}/personas"
personas_result.write.format("delta").mode("overwrite").option("mergeSchema", "true").save(local1)
lake.upload_dir(local1, "gold/personas/")

tmp2 = lake.make_temp_dir("gold_persona_summary_")
local2 = f"{tmp2}/persona_summary"
persona_summary.write.format("delta").mode("overwrite").save(local2)
lake.upload_dir(local2, "gold/persona_summary/")

duration = round(time.time() - start_time, 2)
logger.info(f"Gold personas em {duration}s")
dbutils.notebook.exit(f"SUCCESS in {duration}s")
