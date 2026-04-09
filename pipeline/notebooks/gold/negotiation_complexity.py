# Databricks notebook source
# MAGIC %md
# MAGIC # Gold: Negotiation Complexity
# MAGIC Correlacao entre numero de perguntas e tipo de perguntas com outcome.

import logging
import sys
import time

from pyspark.sql import functions as F

logger = logging.getLogger("gold.negotiation_complexity")

sys.path.insert(0, "/Workspace/Repos/rodrigosiliunas1@gmail.com/agentic-workflow-medallion-pipeline/pipeline")
from pipeline_lib.storage import S3Lake

lake = S3Lake(dbutils)
CATALOG = spark.conf.get("pipeline.catalog", "medallion")
start_time = time.time()

messages = spark.table(f"{CATALOG}.silver.messages_clean")

# ============================================================
# 1. CONTAR PERGUNTAS POR CONVERSA (mensagens com ?)
# ============================================================
inbound = messages.filter(
    (F.col("direction") == "inbound") & (F.col("message_body").isNotNull())
)

questions = inbound.withColumn(
    "is_question", F.col("message_body").contains("?").cast("int")
).withColumn(
    "is_price_question",
    F.when(
        F.col("message_body").rlike("(?i)(preco|valor|custa|parcela|desconto|barato|caro)"),
        1,
    ).otherwise(0),
).withColumn(
    "is_coverage_question",
    F.when(
        F.col("message_body").rlike("(?i)(cobertura|cobre|inclui|protege|assistencia|guincho)"),
        1,
    ).otherwise(0),
)

complexity = questions.groupBy("conversation_id").agg(
    F.sum("is_question").alias("total_questions"),
    F.sum("is_price_question").alias("price_questions"),
    F.sum("is_coverage_question").alias("coverage_questions"),
    F.count("*").alias("total_inbound_messages"),
    F.first("conversation_outcome").alias("outcome"),
)

complexity = complexity.withColumn(
    "question_rate", F.round(F.col("total_questions") / F.col("total_inbound_messages"), 3)
)

# ============================================================
# 2. CORRELACAO PERGUNTAS vs OUTCOME
# ============================================================
by_outcome = complexity.groupBy("outcome").agg(
    F.avg("total_questions").alias("avg_questions"),
    F.avg("price_questions").alias("avg_price_questions"),
    F.avg("coverage_questions").alias("avg_coverage_questions"),
    F.avg("question_rate").alias("avg_question_rate"),
    F.count("*").alias("conversations"),
)

# ============================================================
# 3. SALVAR
# ============================================================
complexity.write.format("delta").mode("overwrite").option("mergeSchema", "true").saveAsTable(
    f"{CATALOG}.gold.negotiation_complexity"
)

by_outcome.write.format("delta").mode("overwrite").saveAsTable(
    f"{CATALOG}.gold.negotiation_by_outcome"
)

# Upload para S3
tmp1 = lake.make_temp_dir("gold_negotiation_")
local1 = f"{tmp1}/negotiation_complexity"
complexity.write.format("delta").mode("overwrite").option("mergeSchema", "true").save(local1)
lake.upload_dir(local1, "gold/negotiation_complexity/")

tmp2 = lake.make_temp_dir("gold_negotiation_outcome_")
local2 = f"{tmp2}/negotiation_by_outcome"
by_outcome.write.format("delta").mode("overwrite").save(local2)
lake.upload_dir(local2, "gold/negotiation_by_outcome/")

duration = round(time.time() - start_time, 2)
logger.info(f"Gold negotiation_complexity em {duration}s")
dbutils.notebook.exit(f"SUCCESS in {duration}s")
