# Databricks notebook source
# MAGIC %md
# MAGIC # Gold: Churn & Reengagement
# MAGIC Detecta leads que pararam de responder (gap > 120 min entre mensagens inbound)
# MAGIC e identifica as mensagens outbound de reativacao que trouxeram o lead de volta.
# MAGIC
# MAGIC **Camada:** Gold | **Dependencia:** silver.messages_clean
# MAGIC **Output:** `gold.churn_reengagement`
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
logger = logging.getLogger("gold.churn_reengagement")
start_time = time.time()

# COMMAND ----------

# DBTITLE 1,Carregar Mensagens
messages = spark.table(f"{CATALOG}.silver.messages_clean")

# COMMAND ----------

# DBTITLE 1,Detectar Gaps de Silencio do Lead
# Filtra apenas mensagens inbound (do lead) e calcula gap entre mensagens consecutivas
inbound = messages.filter(F.col("direction") == "inbound").select(
    "conversation_id", "timestamp", "message_body", "conversation_outcome"
)

# Window para calcular diferenca temporal entre mensagens consecutivas do mesmo lead
w = Window.partitionBy("conversation_id").orderBy("timestamp")
inbound_with_gap = inbound.withColumn(
    "prev_timestamp", F.lag("timestamp").over(w)
).withColumn(
    "gap_minutes",
    (F.unix_timestamp("timestamp") - F.unix_timestamp("prev_timestamp")) / 60,
)

# Gap > 120 minutos (2 horas) e considerado potencial churn temporario
# Indica que o lead parou de responder por um periodo significativo
churn_events = inbound_with_gap.filter(F.col("gap_minutes") > 120)

# COMMAND ----------

# DBTITLE 1,Identificar Mensagem de Reativacao
# Busca a mensagem outbound (do agente) que foi enviada no gap de silencio
# e que antecedeu a volta do lead
outbound = messages.filter(F.col("direction") == "outbound").select(
    "conversation_id",
    F.col("timestamp").alias("out_timestamp"),
    F.col("message_body").alias("reactivation_message"),
)

# Join: mensagens outbound enviadas durante o gap (entre prev_timestamp e timestamp)
reactivated = churn_events.join(outbound, on="conversation_id").filter(
    (F.col("out_timestamp") < F.col("timestamp"))
    & (F.col("out_timestamp") > F.col("prev_timestamp"))
)

# Para cada evento de churn, pega a ultima mensagem de reativacao enviada
w2 = Window.partitionBy(
    reactivated["conversation_id"], reactivated["timestamp"]
).orderBy(F.col("out_timestamp").desc())

reactivation_msgs = (
    reactivated.withColumn("rn", F.row_number().over(w2))
    .filter(F.col("rn") == 1)
    .drop("rn")
)

# COMMAND ----------

# DBTITLE 1,Resumo de Churn por Conversa
# Agrega eventos de churn por conversa: contagem, silencio maximo/medio, outcome
churn_summary = (
    churn_events.groupBy("conversation_id")
    .agg(
        F.count("*").alias("churn_events"),
        F.max("gap_minutes").alias("max_silence_minutes"),
        F.avg("gap_minutes").alias("avg_silence_minutes"),
        F.first("conversation_outcome").alias("outcome"),
    )
    # Flag: conversa foi reengajada se o outcome e positivo
    .withColumn(
        "was_reengaged",
        F.col("outcome").isin("venda_fechada", "em_negociacao", "proposta_enviada"),
    )
)

# COMMAND ----------

# DBTITLE 1,Salvar no Unity Catalog e S3
GOLD_TABLE = f"{CATALOG}.gold.churn_reengagement"
churn_summary.write.format("delta").mode("overwrite").option("mergeSchema", "true").saveAsTable(
    GOLD_TABLE
)

# Backup em Parquet no S3
lake.write_parquet(churn_summary, "gold/churn_reengagement/")

duration = round(time.time() - start_time, 2)
count = churn_summary.count()
logger.info(f"Gold churn_reengagement: {count} conversas com churn em {duration}s")
dbutils.notebook.exit(f"SUCCESS: {count} churn events in {duration}s")
