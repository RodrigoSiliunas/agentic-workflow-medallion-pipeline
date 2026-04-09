# Databricks notebook source
# MAGIC %md
# MAGIC # Gold: Negotiation Complexity
# MAGIC Correlacao entre numero de perguntas e tipo de perguntas com outcome.

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
logger = logging.getLogger("gold.negotiation_complexity")
start_time = time.time()

messages = spark.table(f"{CATALOG}.silver.messages_clean")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Contar Perguntas por Conversa

# COMMAND ----------

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

# COMMAND ----------

# MAGIC %md
# MAGIC ## Correlacao Perguntas vs Outcome

# COMMAND ----------

by_outcome = complexity.groupBy("outcome").agg(
    F.avg("total_questions").alias("avg_questions"),
    F.avg("price_questions").alias("avg_price_questions"),
    F.avg("coverage_questions").alias("avg_coverage_questions"),
    F.avg("question_rate").alias("avg_question_rate"),
    F.count("*").alias("conversations"),
)

# COMMAND ----------

# MAGIC %md
# MAGIC ## Salvar

# COMMAND ----------

complexity.write.format("delta").mode("overwrite").option("mergeSchema", "true").saveAsTable(
    f"{CATALOG}.gold.negotiation_complexity"
)

by_outcome.write.format("delta").mode("overwrite").saveAsTable(
    f"{CATALOG}.gold.negotiation_by_outcome"
)

lake.write_parquet(complexity, "gold/negotiation_complexity/")
lake.write_parquet(by_outcome, "gold/negotiation_by_outcome/")

duration = round(time.time() - start_time, 2)
logger.info(f"Gold negotiation_complexity em {duration}s")
dbutils.notebook.exit(f"SUCCESS in {duration}s")
