# Databricks notebook source
# MAGIC %md
# MAGIC # Gold: Email Providers
# MAGIC Distribuicao de provedores de email dos leads.

# COMMAND ----------

import logging
import sys
import time

from pyspark.sql import functions as F

logger = logging.getLogger("gold.email_providers")

sys.path.insert(0, "/Workspace/Repos/rodrigosiliunas1@gmail.com/agentic-workflow-medallion-pipeline/pipeline")
from pipeline_lib.storage import S3Lake

lake = S3Lake(dbutils)
CATALOG = "medallion"
start_time = time.time()

leads = spark.table(f"{CATALOG}.silver.leads_profile")

# COMMAND ----------

# ============================================================
# 1. EXTRAIR DOMINIO DOS EMAILS MASCARADOS
# ============================================================
# email_masked contem array de emails tipo "j***a@gmail.com"
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

# ============================================================
# 2. AGREGAR
# ============================================================
provider_stats = providers.groupBy("provider", "provider_category").agg(
    F.count("*").alias("total_leads"),
).orderBy(F.col("total_leads").desc())

total_emails = providers.count()
provider_stats = provider_stats.withColumn(
    "pct_of_total", F.round(F.col("total_leads") / F.lit(total_emails) * 100, 2)
)

# COMMAND ----------

# ============================================================
# 3. SALVAR
# ============================================================
GOLD_TABLE = f"{CATALOG}.gold.email_providers"
provider_stats.write.format("delta").mode("overwrite").option("mergeSchema", "true").saveAsTable(
    GOLD_TABLE
)

# Upload para S3
tmp = lake.make_temp_dir("gold_email_")
local_path = f"{tmp}/email_providers"
provider_stats.write.format("delta").mode("overwrite").option("mergeSchema", "true").save(local_path)
lake.upload_dir(local_path, "gold/email_providers/")

duration = round(time.time() - start_time, 2)
logger.info(f"Gold email_providers: {provider_stats.count()} providers em {duration}s")
dbutils.notebook.exit(f"SUCCESS in {duration}s")
