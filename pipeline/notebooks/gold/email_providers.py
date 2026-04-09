# Databricks notebook source
# MAGIC %md
# MAGIC # Gold: Email Providers
# MAGIC Distribuicao de provedores de email dos leads.

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

from pyspark.sql import functions as F

# Auto-detect repo path from this notebook's location
_nb_path = dbutils.notebook.entry_point.getDbutils().notebook().getContext().notebookPath().get()
_repo_root = "/".join(_nb_path.split("/")[:5])
PIPELINE_ROOT = f"/Workspace{_repo_root}/pipeline"
sys.path.insert(0, PIPELINE_ROOT)

from pipeline_lib.storage import S3Lake

lake = S3Lake(dbutils, spark, scope=SCOPE)
logger = logging.getLogger("gold.email_providers")
start_time = time.time()

leads = spark.table(f"{CATALOG}.silver.leads_profile")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Extrair Dominio dos Emails Mascarados

# COMMAND ----------

emails_exploded = leads.select(
    "conversation_id", F.explode_outer("email_masked").alias("email_masked")
).filter(F.col("email_masked").isNotNull())

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

# MAGIC %md
# MAGIC ## Agregar

# COMMAND ----------

provider_stats = providers.groupBy("provider", "provider_category").agg(
    F.count("*").alias("total_leads"),
).orderBy(F.col("total_leads").desc())

total_emails = providers.count()
provider_stats = provider_stats.withColumn(
    "pct_of_total", F.round(F.col("total_leads") / F.lit(total_emails) * 100, 2)
)

# COMMAND ----------

# MAGIC %md
# MAGIC ## Salvar

# COMMAND ----------

GOLD_TABLE = f"{CATALOG}.gold.email_providers"
provider_stats.write.format("delta").mode("overwrite").option("mergeSchema", "true").saveAsTable(
    GOLD_TABLE
)

lake.write_parquet(provider_stats, "gold/email_providers/")

duration = round(time.time() - start_time, 2)
logger.info(f"Gold email_providers: {provider_stats.count()} providers em {duration}s")
dbutils.notebook.exit(f"SUCCESS in {duration}s")
