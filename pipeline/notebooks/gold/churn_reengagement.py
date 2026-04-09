# Databricks notebook source
# MAGIC %md
# MAGIC # Gold: Churn & Reengagement
# MAGIC Leads que pararam de responder e depois voltaram. Mensagens de reativacao.

# COMMAND ----------

import logging
import sys
import time

from pyspark.sql import Window
from pyspark.sql import functions as F

logger = logging.getLogger("gold.churn_reengagement")

sys.path.insert(0, "/Workspace/Repos/rodrigosiliunas1@gmail.com/agentic-workflow-medallion-pipeline/pipeline")
from pipeline_lib.storage import S3Lake

lake = S3Lake(dbutils, spark)
CATALOG = "medallion"
start_time = time.time()

messages = spark.table(f"{CATALOG}.silver.messages_clean")

# COMMAND ----------

# ============================================================
# 1. DETECTAR GAPS DE SILENCIO DO LEAD (> 2h entre mensagens inbound)
# ============================================================
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

# ============================================================
# 2. MENSAGEM DE REATIVACAO (outbound logo antes do retorno)
# ============================================================
outbound = messages.filter(F.col("direction") == "outbound").select(
    "conversation_id",
    F.col("timestamp").alias("out_timestamp"),
    F.col("message_body").alias("reactivation_message"),
)

# Para cada retorno do lead, encontrar a ultima mensagem outbound antes dele
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

# ============================================================
# 3. RESUMO
# ============================================================
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

# ============================================================
# 4. SALVAR
# ============================================================
GOLD_TABLE = f"{CATALOG}.gold.churn_reengagement"
churn_summary.write.format("delta").mode("overwrite").option("mergeSchema", "true").saveAsTable(
    GOLD_TABLE
)

# Upload para S3 (in-memory)
lake.write_parquet(churn_summary, "gold/churn_reengagement/")

duration = round(time.time() - start_time, 2)
count = churn_summary.count()
logger.info(f"Gold churn_reengagement: {count} conversas com churn em {duration}s")
dbutils.notebook.exit(f"SUCCESS: {count} churn events in {duration}s")
