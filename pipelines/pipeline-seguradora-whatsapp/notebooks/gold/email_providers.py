# Databricks notebook source
# MAGIC %md
# MAGIC # Gold: Email Providers
# MAGIC Analisa distribuicao de provedores de email dos leads a partir dos emails
# MAGIC mascarados. Categoriza em Gmail, Microsoft, Yahoo, Apple e Outros.
# MAGIC
# MAGIC **Camada:** Gold | **Dependencia:** silver.leads_profile
# MAGIC **Output:** `gold.email_providers`
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
logger = logging.getLogger("gold.email_providers")
start_time = time.time()

# COMMAND ----------

# DBTITLE 1,Carregar Leads Profile
leads = spark.table(f"{CATALOG}.silver.leads_profile")

# COMMAND ----------

# DBTITLE 1,Extrair Dominio dos Emails Mascarados
# Explode o array de emails mascarados para ter uma linha por email
# O dominio (apos @) e preservado pelo mascaramento format-preserving
emails_exploded = leads.select(
    "conversation_id", F.explode_outer("email_masked").alias("email_masked")
).filter(F.col("email_masked").isNotNull())

# Extrai o dominio e categoriza em providers conhecidos
providers = emails_exploded.withColumn(
    "provider", F.split("email_masked", "@").getItem(1)
).withColumn(
    "provider_category",
    F.when(F.col("provider").contains("gmail"), "Gmail")
    .when(F.col("provider").contains("hotmail") | F.col("provider").contains("outlook"), "Microsoft")
    .when(F.col("provider").contains("yahoo"), "Yahoo")
    .when(F.col("provider").contains("icloud") | F.col("provider").contains("me.com"), "Apple")
    .otherwise("Outros"),
)

# COMMAND ----------

# DBTITLE 1,Agregar Estatisticas por Provider
# Contagem de leads por provider e categoria, ordenado por popularidade
provider_stats = providers.groupBy("provider", "provider_category").agg(
    F.count("*").alias("total_leads"),
).orderBy(F.col("total_leads").desc())

# Percentual de cada provider sobre o total de emails
total_emails = providers.count()
provider_stats = provider_stats.withColumn(
    "pct_of_total", F.round(F.col("total_leads") / F.lit(total_emails) * 100, 2)
)

# COMMAND ----------

# DBTITLE 1,Salvar no Unity Catalog e S3
GOLD_TABLE = f"{CATALOG}.gold.email_providers"
provider_stats.write.format("delta").mode("overwrite").option("mergeSchema", "true").saveAsTable(
    GOLD_TABLE
)

# Backup em Parquet no S3
lake.write_parquet(provider_stats, "gold/email_providers/")

duration = round(time.time() - start_time, 2)
logger.info(f"Gold email_providers: {provider_stats.count()} providers em {duration}s")
dbutils.notebook.exit(f"SUCCESS in {duration}s")
