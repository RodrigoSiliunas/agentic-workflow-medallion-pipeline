# Databricks notebook source
# MAGIC %md
# MAGIC # Quality Validation
# MAGIC Verifica integridade Bronze -> Silver -> Gold apos cada execucao.

# COMMAND ----------

dbutils.widgets.text("catalog", "medallion", "Catalog Name")

CATALOG = dbutils.widgets.get("catalog")

# COMMAND ----------

import logging
import re
import time

from pyspark.sql import functions as F

logger = logging.getLogger("validation.checks")

# COMMAND ----------

try:
    should_process = dbutils.jobs.taskValues.get(
        taskKey="agent_pre", key="should_process", default=True
    )
    if not should_process:
        dbutils.notebook.exit("SKIP")
except Exception:
    pass

start_time = time.time()
errors = []
warnings = []

# COMMAND ----------

# MAGIC %md
# MAGIC ## Bronze Checks

# COMMAND ----------

try:
    bronze = spark.table(f"{CATALOG}.bronze.conversations")
    bronze_count = bronze.count()

    if bronze_count == 0:
        errors.append("Bronze vazia (0 linhas)")
    else:
        logger.info(f"Bronze: {bronze_count} linhas OK")
except Exception as e:
    errors.append(f"Bronze nao existe ou erro: {e}")
    bronze_count = 0

# COMMAND ----------

# MAGIC %md
# MAGIC ## Silver Checks

# COMMAND ----------

try:
    messages = spark.table(f"{CATALOG}.silver.messages_clean")
    messages_count = messages.count()

    if bronze_count > 0 and messages_count >= bronze_count:
        warnings.append(
            f"Silver messages_clean ({messages_count}) >= Bronze ({bronze_count}). "
            "Dedup nao removeu linhas?"
        )

    if bronze_count > 0 and messages_count < bronze_count * 0.85:
        errors.append(
            f"Silver perdeu mais de 15% das linhas: {messages_count}/{bronze_count}"
        )

    # Verificar que message_body nao contem PII em texto claro
    CPF_PATTERN = r"\b\d{3}\.\d{3}\.\d{3}-\d{2}\b"
    sample = messages.select("message_body").limit(500).collect()
    pii_found = 0
    for row in sample:
        if row.message_body and re.search(CPF_PATTERN, str(row.message_body)):
            pii_found += 1

    if pii_found > 0:
        errors.append(f"PII detectado em {pii_found} mensagens da Silver (CPF em texto claro)")

    logger.info(f"Silver messages_clean: {messages_count} linhas")
except Exception as e:
    errors.append(f"Silver messages_clean nao existe: {e}")

try:
    leads = spark.table(f"{CATALOG}.silver.leads_profile")
    leads_count = leads.count()
    logger.info(f"Silver leads_profile: {leads_count} leads")

    lead_cols = set(leads.columns)
    expected = {"cpf_masked", "email_masked", "phone_masked", "plate_masked"}
    missing = expected - lead_cols
    if missing:
        errors.append(f"Silver leads_profile faltando colunas: {missing}")
except Exception as e:
    errors.append(f"Silver leads_profile nao existe: {e}")

try:
    convs = spark.table(f"{CATALOG}.silver.conversations_enriched")
    convs_count = convs.count()
    logger.info(f"Silver conversations_enriched: {convs_count} conversas")
except Exception as e:
    errors.append(f"Silver conversations_enriched nao existe: {e}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Gold Checks

# COMMAND ----------

gold_tables = [
    "funil_vendas", "agent_performance", "sentiment", "lead_scoring",
    "email_providers", "temporal_analysis", "competitor_intel", "campaign_roi",
    "personas", "churn_reengagement", "negotiation_complexity",
    "first_contact_resolution",
]

for table_name in gold_tables:
    full_name = f"{CATALOG}.gold.{table_name}"
    try:
        count = spark.table(full_name).count()
        if count == 0:
            warnings.append(f"Gold {table_name} vazia (0 linhas)")
        else:
            logger.info(f"Gold {table_name}: {count} linhas OK")
    except Exception as e:
        errors.append(f"Gold {table_name} nao existe: {e}")

# Lead scoring range check
try:
    scores = spark.table(f"{CATALOG}.gold.lead_scoring")
    min_score = scores.agg(F.min("lead_score")).first()[0]
    max_score = scores.agg(F.max("lead_score")).first()[0]
    if min_score is not None and (min_score < 0 or max_score > 100):
        errors.append(f"Lead scores fora do range 0-100: min={min_score}, max={max_score}")
except Exception:
    pass

# Sentiment range check
try:
    sent = spark.table(f"{CATALOG}.gold.sentiment")
    min_s = sent.agg(F.min("sentiment_score")).first()[0]
    max_s = sent.agg(F.max("sentiment_score")).first()[0]
    if min_s is not None and (min_s < -1.0 or max_s > 1.0):
        errors.append(f"Sentiment fora do range -1/+1: min={min_s}, max={max_s}")
except Exception:
    pass

# COMMAND ----------

# MAGIC %md
# MAGIC ## Resultado

# COMMAND ----------

duration = round(time.time() - start_time, 2)
status = "PASS" if len(errors) == 0 else "FAIL"

result = {
    "status": status,
    "errors": errors,
    "warnings": warnings,
    "duration_sec": duration,
}

logger.info(f"Validation: {status} ({len(errors)} errors, {len(warnings)} warnings) em {duration}s")

try:
    dbutils.jobs.taskValues.set(key="status", value=status)
    dbutils.jobs.taskValues.set(key="errors", value=str(errors) if errors else "none")
    dbutils.jobs.taskValues.set(key="warnings", value=str(warnings) if warnings else "none")
except Exception:
    pass

if errors:
    dbutils.notebook.exit(f"FAIL: {len(errors)} errors: {errors}")
else:
    dbutils.notebook.exit(f"PASS: {len(warnings)} warnings in {duration}s")
