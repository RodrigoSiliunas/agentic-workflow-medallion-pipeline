# Databricks notebook source
# MAGIC %md
# MAGIC # Gold: Funil de Conversao
# MAGIC Analisa distribuicao de outcomes por etapa do funil, calcula taxa de conversao,
# MAGIC identifica a "mensagem fatal" (ultima outbound antes de ghosting), e determina
# MAGIC o ponto de abandono medio por outcome.
# MAGIC
# MAGIC **Camada:** Gold | **Dependencia:** silver.messages_clean, silver.conversations_enriched
# MAGIC **Output:** `gold.funil_vendas`, `gold.fatal_messages`
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
logger = logging.getLogger("gold.funnel")
start_time = time.time()

# COMMAND ----------

# DBTITLE 1,Carregar Tabelas Silver
# Carrega mensagens e conversas enriquecidas da camada Silver
messages = spark.table(f"{CATALOG}.silver.messages_clean")
conversations = spark.table(f"{CATALOG}.silver.conversations_enriched")

# COMMAND ----------

# DBTITLE 1,Distribuicao de Outcomes
# Calcula estatisticas por outcome: contagem, media de mensagens, duracao, response time
outcome_dist = conversations.groupBy("outcome").agg(
    F.count("*").alias("total_conversations"),
    F.avg("total_messages").alias("avg_messages"),
    F.avg("duration_minutes").alias("avg_duration_min"),
    F.avg("avg_response_time_sec").alias("avg_response_time"),
)

# Percentual de cada outcome sobre o total de conversas
total = conversations.count()
outcome_dist = outcome_dist.withColumn(
    "pct_of_total", F.round(F.col("total_conversations") / F.lit(total) * 100, 2)
)

# COMMAND ----------

# DBTITLE 1,Mensagem Fatal (ultima outbound antes de ghosting)
# Identifica a ultima mensagem enviada pelo agente em conversas que terminaram em ghosting
# Objetivo: descobrir padroes de mensagens que "matam" a conversa
ghost_convs = messages.filter(F.col("conversation_outcome") == "ghosting")

# Window para pegar a ultima mensagem outbound de cada conversa ghost
w = Window.partitionBy("conversation_id").orderBy(F.col("timestamp").desc())
last_outbound = (
    ghost_convs.filter(F.col("direction") == "outbound")
    .withColumn("rn", F.row_number().over(w))
    .filter(F.col("rn") == 1)
    .select("conversation_id", F.col("message_body").alias("fatal_message"))
)

# Agrupa por primeiras 10 palavras para encontrar padroes recorrentes
fatal_patterns = (
    last_outbound.withColumn(
        "msg_truncated",
        F.concat_ws(" ", F.slice(F.split("fatal_message", r"\s+"), 1, 10)),
    )
    .groupBy("msg_truncated")
    .agg(F.count("*").alias("frequency"))
    .orderBy(F.col("frequency").desc())
    .limit(50)
)

# COMMAND ----------

# DBTITLE 1,Ponto de Abandono
# Calcula em qual mensagem (sequencial) o lead para de responder por outcome
# Util para saber se leads desistem cedo ou tarde na conversa
msg_seq = messages.withColumn(
    "msg_number",
    F.row_number().over(Window.partitionBy("conversation_id").orderBy("timestamp")),
)

# Ultima mensagem inbound de cada conversa (quando o lead parou de falar)
last_inbound_per_conv = (
    msg_seq.filter(F.col("direction") == "inbound")
    .groupBy("conversation_id")
    .agg(F.max("msg_number").alias("last_inbound_msg_number"))
)

# Media e mediana do ponto de abandono por outcome
abandonment_point = (
    last_inbound_per_conv.join(
        conversations.select("conversation_id", "outcome"), on="conversation_id"
    )
    .groupBy("outcome")
    .agg(
        F.avg("last_inbound_msg_number").alias("avg_last_inbound_msg"),
        F.percentile_approx("last_inbound_msg_number", 0.5).alias("median_last_inbound_msg"),
    )
)

# COMMAND ----------

# DBTITLE 1,Combinar e Salvar
# Junta distribuicao de outcomes com ponto de abandono
funnel = outcome_dist.join(abandonment_point, on="outcome", how="left")

GOLD_TABLE = f"{CATALOG}.gold.funil_vendas"
funnel.write.format("delta").mode("overwrite").option("mergeSchema", "true").saveAsTable(GOLD_TABLE)

# Salva fatal_messages como tabela separada
fatal_patterns.write.format("delta").mode("overwrite").saveAsTable(
    f"{CATALOG}.gold.fatal_messages"
)

# Backup em Parquet no S3
lake.write_parquet(funnel, "gold/funil_vendas/")
lake.write_parquet(fatal_patterns, "gold/fatal_messages/")

duration = round(time.time() - start_time, 2)
logger.info(f"Gold funil_vendas: {funnel.count()} rows em {duration}s")
dbutils.notebook.exit(f"SUCCESS: funnel + fatal_messages in {duration}s")
