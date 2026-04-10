# Databricks notebook source
# MAGIC %md
# MAGIC # Gold: Competitor Intelligence
# MAGIC Analisa concorrentes mencionados pelos leads nas conversas: frequencia de mencao,
# MAGIC taxa de perda quando mencionado, precos citados, e taxa de venda apesar da mencao.
# MAGIC
# MAGIC **Camada:** Gold | **Dependencia:** silver.leads_profile, silver.conversations_enriched
# MAGIC **Output:** `gold.competitor_intel`
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
logger = logging.getLogger("gold.competitor_intel")
start_time = time.time()

# COMMAND ----------

# DBTITLE 1,Carregar Tabelas Silver
leads = spark.table(f"{CATALOG}.silver.leads_profile")
conversations = spark.table(f"{CATALOG}.silver.conversations_enriched")

# COMMAND ----------

# DBTITLE 1,Explodir Concorrentes por Conversa
# Junta leads com outcome da conversa e explode o array de concorrentes mencionados
leads_with_outcome = leads.join(
    conversations.select("conversation_id", "outcome"), on="conversation_id"
)

# Cada mencao de concorrente vira uma linha separada
competitors = leads_with_outcome.select(
    "conversation_id",
    "outcome",
    F.explode_outer("competitors_mentioned").alias("competitor"),
    "prices_mentioned",
).filter(F.col("competitor").isNotNull())

# COMMAND ----------

# DBTITLE 1,Metricas por Concorrente
# Calcula para cada concorrente: contagem de mencoes, perdas, vendas e preco medio
comp_stats = competitors.groupBy("competitor").agg(
    F.count("*").alias("mention_count"),
    # Quantas vezes perdemos quando este concorrente foi mencionado
    F.sum(
        F.when(F.col("outcome").isin("perdido_concorrente", "perdido_preco"), 1).otherwise(0)
    ).alias("losses_when_mentioned"),
    # Quantas vezes ganhamos apesar da mencao ao concorrente
    F.sum(F.when(F.col("outcome") == "venda_fechada", 1).otherwise(0)).alias(
        "wins_despite_mention"
    ),
    # Preco medio mencionado (primeiro preco de cada conversa como proxy)
    F.avg(F.col("prices_mentioned").getItem(0)).alias("avg_competitor_price_mentioned"),
)

# Calcula taxas percentuais de perda e vitoria
comp_stats = comp_stats.withColumns(
    {
        "loss_rate": F.round(
            F.col("losses_when_mentioned") / F.col("mention_count") * 100, 2
        ),
        "win_despite_rate": F.round(
            F.col("wins_despite_mention") / F.col("mention_count") * 100, 2
        ),
    }
).orderBy(F.col("mention_count").desc())

# COMMAND ----------

# DBTITLE 1,Salvar no Unity Catalog e S3
GOLD_TABLE = f"{CATALOG}.gold.competitor_intel"
comp_stats.write.format("delta").mode("overwrite").option("mergeSchema", "true").saveAsTable(
    GOLD_TABLE
)

# Backup em Parquet no S3
lake.write_parquet(comp_stats, "gold/competitor_intel/")

duration = round(time.time() - start_time, 2)
logger.info(f"Gold competitor_intel: {comp_stats.count()} concorrentes em {duration}s")
dbutils.notebook.exit(f"SUCCESS in {duration}s")
