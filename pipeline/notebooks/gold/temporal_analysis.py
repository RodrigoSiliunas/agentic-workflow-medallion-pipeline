# Databricks notebook source
# MAGIC %md
# MAGIC # Gold: Temporal Analysis
# MAGIC Heatmap de conversao por hora x dia da semana. Identifica horarios otimos
# MAGIC de contato para maximizar taxa de conversao e melhor horario por dia.
# MAGIC
# MAGIC **Camada:** Gold | **Dependencia:** silver.conversations_enriched
# MAGIC **Output:** `gold.temporal_analysis`
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
logger = logging.getLogger("gold.temporal_analysis")
start_time = time.time()

# COMMAND ----------

# DBTITLE 1,Carregar Conversas Enriquecidas
conversations = spark.table(f"{CATALOG}.silver.conversations_enriched")

# COMMAND ----------

# DBTITLE 1,Heatmap: Hora x Dia da Semana x Conversao
# Agrupa por hora e dia da semana do primeiro contato para criar heatmap
# Calcula total de contatos, vendas, response time e media de mensagens
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
    # Taxa de conversao percentual para cada slot hora x dia
    .withColumn("conversion_rate", F.round(F.col("wins") / F.col("total_contacts") * 100, 2))
    .orderBy("contact_dow", "contact_hour")
)

# COMMAND ----------

# DBTITLE 1,Melhor Horario por Dia da Semana
# Para cada dia da semana, identifica a hora com maior taxa de conversao
w = Window.partitionBy("contact_dow").orderBy(F.col("conversion_rate").desc())
best_hours = temporal.withColumn("rank", F.row_number().over(w)).filter(F.col("rank") == 1).drop(
    "rank"
)

# COMMAND ----------

# DBTITLE 1,Salvar no Unity Catalog e S3
GOLD_TABLE = f"{CATALOG}.gold.temporal_analysis"
temporal.write.format("delta").mode("overwrite").option("mergeSchema", "true").saveAsTable(
    GOLD_TABLE
)

# Backup em Parquet no S3
lake.write_parquet(temporal, "gold/temporal_analysis/")

duration = round(time.time() - start_time, 2)
logger.info(f"Gold temporal_analysis em {duration}s")
dbutils.notebook.exit(f"SUCCESS in {duration}s")
