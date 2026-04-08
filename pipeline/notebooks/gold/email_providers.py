# Databricks notebook source
# MAGIC %md
# MAGIC # Gold: Email Providers
# MAGIC Distribuicao de provedores de email dos leads.

import logging
import time

from pyspark.sql import functions as F

logger = logging.getLogger("gold.email_providers")
CATALOG = spark.conf.get("pipeline.catalog", "medallion")
start_time = time.time()

leads = spark.table(f"{CATALOG}.silver.leads_profile")

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

# ============================================================
# 3. SALVAR
# ============================================================
GOLD_TABLE = f"{CATALOG}.gold.email_providers"
provider_stats.write.format("delta").mode("overwrite").option("mergeSchema", "true").saveAsTable(
    GOLD_TABLE
)

duration = round(time.time() - start_time, 2)
logger.info(f"Gold email_providers: {provider_stats.count()} providers em {duration}s")
dbutils.notebook.exit(f"SUCCESS in {duration}s")
