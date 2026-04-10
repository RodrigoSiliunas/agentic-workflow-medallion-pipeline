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

from pyspark.sql import functions as F

# Auto-detect repo path from this notebook's location
_nb_path = dbutils.notebook.entry_point.getDbutils().notebook().getContext().notebookPath().get()
_repo_root = "/".join(_nb_path.split("/")[:4])
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
# Calcula metricas agregadas para cada conversation_id:
# - Contagens: total, inbound, outbound
# - Timestamps: primeiro e ultimo contato
# - Contexto: outcome, campanha, agente, cidade, estado, device, lead_source
# - Performance: response time medio, mensagens em horario comercial
# - Tipos: lista de message_types usados na conversa
conversations = df.groupBy("conversation_id").agg(
    F.count("*").alias("total_messages"),
    F.sum(F.when(F.col("direction") == "inbound", 1).otherwise(0)).alias("inbound_count"),
    F.sum(F.when(F.col("direction") == "outbound", 1).otherwise(0)).alias("outbound_count"),
    F.min("timestamp").alias("first_message_at"),
    F.max("timestamp").alias("last_message_at"),
    F.first("conversation_outcome").alias("outcome"),
    F.first("campaign_id").alias("campaign_id"),
    F.first("agent_id").alias("agent_id"),
    F.first("meta_city").alias("city"),
    F.first("meta_state").alias("state"),
    F.first("meta_device").alias("device"),
    F.first("meta_lead_source").alias("lead_source"),
    F.avg("meta_response_time_sec").alias("avg_response_time_sec"),
    F.sum(
        F.when(F.col("meta_is_business_hours") == True, 1).otherwise(0)  # noqa: E712
    ).alias("business_hours_messages"),
    F.collect_set("message_type").alias("message_types_used"),
)

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
