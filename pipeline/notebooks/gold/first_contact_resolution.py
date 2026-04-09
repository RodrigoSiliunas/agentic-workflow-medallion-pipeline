# Databricks notebook source
# MAGIC %md
# MAGIC # Gold: First Contact Resolution
# MAGIC Analisa percentual de vendas fechadas na primeira conversa vs leads que
# MAGIC precisaram de multiplos contatos. Identifica leads recorrentes pelo telefone.
# MAGIC
# MAGIC **Camada:** Gold | **Dependencia:** silver.leads_profile, silver.conversations_enriched
# MAGIC **Output:** `gold.first_contact_resolution`, `gold.fcr_summary`
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
logger = logging.getLogger("gold.first_contact_resolution")
start_time = time.time()

# COMMAND ----------

# DBTITLE 1,Carregar Tabelas Silver
leads = spark.table(f"{CATALOG}.silver.leads_profile")
conversations = spark.table(f"{CATALOG}.silver.conversations_enriched")

# COMMAND ----------

# DBTITLE 1,Identificar Mesmo Lead em Conversas Diferentes
# Junta leads com conversas para associar telefone ao outcome
leads_with_conv = leads.join(
    conversations.select("conversation_id", "outcome", "first_message_at"),
    on="conversation_id",
)

# Seleciona campos necessarios para analise de contatos
lead_contacts = leads_with_conv.select(
    "conversation_id", "lead_phone", "outcome", "first_message_at"
)

# Numera os contatos de cada lead por telefone (ordem cronologica)
w = Window.partitionBy("lead_phone").orderBy("first_message_at")
lead_contacts = lead_contacts.withColumn(
    "contact_number", F.row_number().over(w)
).withColumn(
    # Total de contatos deste lead (para saber se e recorrente)
    "total_contacts", F.count("*").over(Window.partitionBy("lead_phone"))
)

# COMMAND ----------

# DBTITLE 1,Calcular First Contact Resolution
# Flag: venda fechada ja no primeiro contato
fcr = lead_contacts.withColumn(
    "is_first_contact_win",
    (F.col("contact_number") == 1) & (F.col("outcome") == "venda_fechada"),
)

# Resumo por lead: total de conversas, total de vendas, primeiro contato com venda
fcr_summary = lead_contacts.groupBy("lead_phone").agg(
    F.count("*").alias("total_conversations"),
    F.sum(F.when(F.col("outcome") == "venda_fechada", 1).otherwise(0)).alias("total_wins"),
    F.min("contact_number").alias("first_win_contact"),
)

# Classifica o tipo de resolucao:
# - first_contact_resolution: vendeu na primeira e unica conversa
# - multi_contact_resolution: vendeu mas precisou de mais de uma conversa
# - no_resolution: nenhuma venda registrada
fcr_stats = fcr_summary.withColumn(
    "resolution_type",
    F.when(
        (F.col("total_wins") > 0) & (F.col("total_conversations") == 1),
        "first_contact_resolution",
    )
    .when(
        (F.col("total_wins") > 0) & (F.col("total_conversations") > 1),
        "multi_contact_resolution",
    )
    .when(F.col("total_wins") == 0, "no_resolution")
    .otherwise("unknown"),
)

# COMMAND ----------

# DBTITLE 1,Metricas Agregadas por Tipo de Resolucao
# Quantos leads em cada tipo e media de contatos necessarios
overall = fcr_stats.groupBy("resolution_type").agg(
    F.count("*").alias("leads"),
    F.avg("total_conversations").alias("avg_contacts"),
)

# Percentual de cada tipo sobre o total de leads
total_leads = fcr_stats.count()
overall = overall.withColumn(
    "pct_of_total", F.round(F.col("leads") / F.lit(total_leads) * 100, 2)
)

# COMMAND ----------

# DBTITLE 1,Salvar no Unity Catalog e S3
# Tabela detalhada por lead
fcr_stats.write.format("delta").mode("overwrite").option("mergeSchema", "true").saveAsTable(
    f"{CATALOG}.gold.first_contact_resolution"
)

# Tabela resumo por tipo de resolucao
overall.write.format("delta").mode("overwrite").saveAsTable(
    f"{CATALOG}.gold.fcr_summary"
)

# Backup em Parquet no S3
lake.write_parquet(fcr_stats, "gold/first_contact_resolution/")
lake.write_parquet(overall, "gold/fcr_summary/")

duration = round(time.time() - start_time, 2)
logger.info(f"Gold first_contact_resolution em {duration}s")
dbutils.notebook.exit(f"SUCCESS in {duration}s")
