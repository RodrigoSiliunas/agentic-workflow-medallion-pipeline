# Databricks notebook source
# MAGIC %md
# MAGIC # Gold: Temporal Analysis
# MAGIC Heatmap de conversao por hora x dia da semana. Horarios otimos de contato.

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
logger = logging.getLogger("gold.temporal_analysis")
start_time = time.time()

conversations = spark.table(f"{CATALOG}.silver.conversations_enriched")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Heatmap: Hora x Dia da Semana x Conversao

# COMMAND ----------

temporal = (
    conversations.withColumn("contact_hour", F.hour("first_message_at"))
    .withColumn("contact_dow", F.dayofweek("first_message_at"))
    .withColumn("dow_name", F.date_format("first_message_at", "EEEE"))
    .groupBy("contact_hour", "contact_dow", "dow_name")
    .agg(
        F.count("*").alias("total_contacts"),
        F.sum(F.when(F.col("outcome") == "venda_fechada", 1).otherwise(0)).alias("wins"),
        F.avg("avg_response_time_sec").alias("avg_response_time"),
        F.avg("total_messages").alias("avg_messages"),
    )
    .withColumn("conversion_rate", F.round(F.col("wins") / F.col("total_contacts") * 100, 2))
    .orderBy("contact_dow", "contact_hour")
)

# COMMAND ----------

# MAGIC %md
# MAGIC ## Melhor Horario por Dia

# COMMAND ----------

w = Window.partitionBy("contact_dow").orderBy(F.col("conversion_rate").desc())
best_hours = temporal.withColumn("rank", F.row_number().over(w)).filter(F.col("rank") == 1).drop(
    "rank"
)

# COMMAND ----------

# MAGIC %md
# MAGIC ## Salvar

# COMMAND ----------

GOLD_TABLE = f"{CATALOG}.gold.temporal_analysis"
temporal.write.format("delta").mode("overwrite").option("mergeSchema", "true").saveAsTable(
    GOLD_TABLE
)

lake.write_parquet(temporal, "gold/temporal_analysis/")

duration = round(time.time() - start_time, 2)
logger.info(f"Gold temporal_analysis em {duration}s")
dbutils.notebook.exit(f"SUCCESS in {duration}s")
