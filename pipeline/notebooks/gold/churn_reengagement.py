# Databricks notebook source
# MAGIC %md
# MAGIC # Gold: Churn & Reengagement
# MAGIC Leads que pararam de responder e depois voltaram. Mensagens de reativacao.

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
logger = logging.getLogger("gold.churn_reengagement")
start_time = time.time()

messages = spark.table(f"{CATALOG}.silver.messages_clean")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Detectar Gaps de Silencio do Lead

# COMMAND ----------

inbound = messages.filter(F.col("direction") == "inbound").select(
    "conversation_id", "timestamp", "message_body", "conversation_outcome"
)

w = Window.partitionBy("conversation_id").orderBy("timestamp")
inbound_with_gap = inbound.withColumn(
    "prev_timestamp", F.lag("timestamp").over(w)
).withColumn(
    "gap_minutes",
    (F.unix_timestamp("timestamp") - F.unix_timestamp("prev_timestamp")) / 60,
)

# Gap > 120 min = potencial churn temporario
churn_events = inbound_with_gap.filter(F.col("gap_minutes") > 120)

# COMMAND ----------

# MAGIC %md
# MAGIC ## Mensagem de Reativacao

# COMMAND ----------

outbound = messages.filter(F.col("direction") == "outbound").select(
    "conversation_id",
    F.col("timestamp").alias("out_timestamp"),
    F.col("message_body").alias("reactivation_message"),
)

reactivated = churn_events.join(outbound, on="conversation_id").filter(
    (F.col("out_timestamp") < F.col("timestamp"))
    & (F.col("out_timestamp") > F.col("prev_timestamp"))
)

w2 = Window.partitionBy(
    reactivated["conversation_id"], reactivated["timestamp"]
).orderBy(F.col("out_timestamp").desc())

reactivation_msgs = (
    reactivated.withColumn("rn", F.row_number().over(w2))
    .filter(F.col("rn") == 1)
    .drop("rn")
)

# COMMAND ----------

# MAGIC %md
# MAGIC ## Resumo

# COMMAND ----------

churn_summary = (
    churn_events.groupBy("conversation_id")
    .agg(
        F.count("*").alias("churn_events"),
        F.max("gap_minutes").alias("max_silence_minutes"),
        F.avg("gap_minutes").alias("avg_silence_minutes"),
        F.first("conversation_outcome").alias("outcome"),
    )
    .withColumn(
        "was_reengaged",
        F.col("outcome").isin("venda_fechada", "em_negociacao", "proposta_enviada"),
    )
)

# COMMAND ----------

# MAGIC %md
# MAGIC ## Salvar

# COMMAND ----------

GOLD_TABLE = f"{CATALOG}.gold.churn_reengagement"
churn_summary.write.format("delta").mode("overwrite").option("mergeSchema", "true").saveAsTable(
    GOLD_TABLE
)

lake.write_parquet(churn_summary, "gold/churn_reengagement/")

duration = round(time.time() - start_time, 2)
count = churn_summary.count()
logger.info(f"Gold churn_reengagement: {count} conversas com churn em {duration}s")
dbutils.notebook.exit(f"SUCCESS: {count} churn events in {duration}s")
