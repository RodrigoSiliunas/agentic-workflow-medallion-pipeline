# Databricks notebook source
# MAGIC %md
# MAGIC # Silver Task 2c: Conversation Enrichment
# MAGIC Agrega metricas por conversa a partir das mensagens limpas: total de mensagens,
# MAGIC duracao, response_time medio, contagem inbound/outbound, tipos de mensagem, etc.
# MAGIC
# MAGIC **Camada:** Silver | **Dependencia:** silver.messages_clean
# MAGIC **Output:** `silver.conversations_enriched`
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
_repo_root = "/".join(_nb_path.split("/")[:4])
PIPELINE_ROOT = f"/Workspace{_repo_root}/pipelines/pipeline-seguradora-whatsapp"
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
logger = logging.getLogger("silver.enrichment")

# COMMAND ----------

# DBTITLE 1,Configuracao de Tabelas
# Tabela de entrada (messages_clean) e saida (conversations_enriched)
SILVER_MESSAGES = f"{CATALOG}.silver.messages_clean"
SILVER_CONVERSATIONS = f"{CATALOG}.silver.conversations_enriched"

# Marca inicio para medir duracao
start_time = time.time()

# COMMAND ----------

# DBTITLE 1,Ler Messages Clean
df = spark.table(SILVER_MESSAGES)

# COMMAND ----------

# DBTITLE 1,Agregar Metricas por Conversa
# T5: F.first() sem orderBy era nao-deterministico. Separamos agregacoes
# puras (count/sum/avg) de "pegar a primeira mensagem por conversation_id"
# que agora usa Window explicita ordenada por timestamp ascendente.

# Agregacoes puras — totalmente determinísticas independente de ordem
aggs = df.groupBy("conversation_id").agg(
    F.count("*").alias("total_messages"),
    F.sum(F.when(F.col("direction") == "inbound", 1).otherwise(0)).alias("inbound_count"),
    F.sum(F.when(F.col("direction") == "outbound", 1).otherwise(0)).alias("outbound_count"),
    F.min("timestamp").alias("first_message_at"),
    F.max("timestamp").alias("last_message_at"),
    F.avg("meta_response_time_sec").alias("avg_response_time_sec"),
    F.sum(
        F.when(F.col("meta_is_business_hours") == True, 1).otherwise(0)  # noqa: E712
    ).alias("business_hours_messages"),
    F.collect_set("message_type").alias("message_types_used"),
)

# Campos pegos da PRIMEIRA mensagem da conversa (por timestamp asc).
# Window.orderBy + row_number = escolha deterministica entre runs.
first_msg_w = Window.partitionBy("conversation_id").orderBy(F.col("timestamp").asc())
first_msg = (
    df.withColumn("_rn", F.row_number().over(first_msg_w))
    .filter(F.col("_rn") == 1)
    .select(
        F.col("conversation_id"),
        F.col("conversation_outcome").alias("outcome"),
        F.col("campaign_id").alias("campaign_id"),
        F.col("agent_id").alias("agent_id"),
        F.col("meta_city").alias("city"),
        F.col("meta_state").alias("state"),
        F.col("meta_device").alias("device"),
        F.col("meta_lead_source").alias("lead_source"),
    )
)

conversations = aggs.join(first_msg, on="conversation_id", how="left")

# Calcula duracao da conversa em minutos (diferenca entre ultima e primeira mensagem)
conversations = conversations.withColumn(
    "duration_minutes",
    (F.unix_timestamp("last_message_at") - F.unix_timestamp("first_message_at")) / 60,
)

# COMMAND ----------

# DBTITLE 1,Salvar no Unity Catalog e S3
# Salva com merge de schema para aceitar colunas novas
(
    conversations.write.format("delta")
    .mode("overwrite")
    .option("mergeSchema", "true")
    .saveAsTable(SILVER_CONVERSATIONS)
)

conv_count = spark.table(SILVER_CONVERSATIONS).count()

# Backup em Parquet no S3
lake.write_parquet(conversations, "silver/conversations_enriched/")
logger.info("Parquet uploaded para S3 silver/conversations_enriched/")

duration = round(time.time() - start_time, 2)
logger.info(f"Silver conversations_enriched: {conv_count} conversas em {duration}s")

# COMMAND ----------

# DBTITLE 1,Metricas e Task Values
# Seta task values (disponiveis para o Observer em caso de falha)
try:
    dbutils.jobs.taskValues.set(key="status", value="SUCCESS")
    dbutils.jobs.taskValues.set(key="rows_output", value=conv_count)
    dbutils.jobs.taskValues.set(key="duration_sec", value=duration)
except Exception:
    pass

dbutils.notebook.exit(f"SUCCESS: {conv_count} conversations enriched in {duration}s")
