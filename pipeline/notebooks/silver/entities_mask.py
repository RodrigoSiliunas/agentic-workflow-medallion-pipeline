# Databricks notebook source
# MAGIC %md
# MAGIC # Silver Task 2b: Entity Extraction + Masking + Redaction
# MAGIC Extrai entidades (CPF, email, phone, plate, vehicle, CEP, competitor, price),
# MAGIC mascara dados sensiveis, e aplica redaction no message_body.

import logging
import sys
import time

from pyspark.sql import functions as F
from pyspark.sql.types import ArrayType, FloatType, StringType

logger = logging.getLogger("silver.entities_mask")

# ============================================================
# TASK VALUES
# ============================================================
try:
    should_process = dbutils.jobs.taskValues.get(
        taskKey="agent_pre", key="should_process", default=True
    )
    if not should_process:
        dbutils.notebook.exit("SKIP")
except Exception:
    pass

# ============================================================
# IMPORTAR LIB (via Databricks Repos ou wheel)
# ============================================================
sys.path.insert(0, "/Workspace/Repos/rodrigosiliunas1@gmail.com/agentic-workflow-medallion-pipeline/pipeline")

from pipeline_lib.storage import S3Lake
from pipeline_lib.extractors import competitor, cpf, cep, email, phone, plate, price, vehicle

lake = S3Lake(dbutils)
from pipeline_lib.masking.format_preserving import mask_cpf, mask_email, mask_phone, mask_plate
from pipeline_lib.masking.hash_based import hash_value
from pipeline_lib.masking.redaction import redact_message_body

# ============================================================
# CONFIGURACAO
# ============================================================
CATALOG = spark.conf.get("pipeline.catalog", "medallion")
SILVER_MESSAGES = f"{CATALOG}.silver.messages_clean"
SILVER_LEADS = f"{CATALOG}.silver.leads_profile"

start_time = time.time()

# ============================================================
# REGISTRAR UDFs
# ============================================================
extract_cpf_udf = F.udf(cpf.extract, ArrayType(StringType()))
extract_email_udf = F.udf(email.extract, ArrayType(StringType()))
extract_phone_udf = F.udf(phone.extract, ArrayType(StringType()))
extract_plate_udf = F.udf(plate.extract, ArrayType(StringType()))
extract_cep_udf = F.udf(cep.extract, ArrayType(StringType()))
extract_competitor_udf = F.udf(competitor.extract, ArrayType(StringType()))
extract_price_udf = F.udf(price.extract, ArrayType(FloatType()))

mask_cpf_udf = F.udf(mask_cpf, StringType())
mask_email_udf = F.udf(mask_email, StringType())
mask_phone_udf = F.udf(mask_phone, StringType())
mask_plate_udf = F.udf(mask_plate, StringType())
hash_udf = F.udf(hash_value, StringType())
redact_udf = F.udf(redact_message_body, StringType())

# ============================================================
# 1. LER MESSAGES_CLEAN (apenas inbound com texto)
# ============================================================
df = spark.table(SILVER_MESSAGES)
df_inbound = df.filter(
    (F.col("direction") == "inbound")
    & (F.col("message_body").isNotNull())
    & (F.col("message_body") != "")
)

# ============================================================
# 2. EXTRAIR ENTIDADES
# ============================================================
df_entities = df_inbound.withColumns(
    {
        "cpfs_found": extract_cpf_udf("message_body"),
        "emails_found": extract_email_udf("message_body"),
        "phones_found": extract_phone_udf("message_body"),
        "plates_found": extract_plate_udf("message_body"),
        "ceps_found": extract_cep_udf("message_body"),
        "competitors_found": extract_competitor_udf("message_body"),
        "prices_found": extract_price_udf("message_body"),
    }
)

# ============================================================
# 3. AGREGAR POR CONVERSA -> LEADS PROFILE
# ============================================================
leads = (
    df_entities.groupBy("conversation_id")
    .agg(
        F.flatten(F.collect_set("cpfs_found")).alias("cpfs"),
        F.flatten(F.collect_set("emails_found")).alias("emails"),
        F.flatten(F.collect_set("phones_found")).alias("phones"),
        F.flatten(F.collect_set("plates_found")).alias("plates"),
        F.flatten(F.collect_set("ceps_found")).alias("ceps"),
        F.flatten(F.collect_set("competitors_found")).alias("competitors_mentioned"),
        F.flatten(F.collect_set("prices_found")).alias("prices_mentioned"),
        F.first("sender_name_normalized").alias("lead_name"),
        F.first("sender_phone").alias("lead_phone"),
    )
)

# ============================================================
# 4. MASCARAR DADOS SENSIVEIS
# ============================================================
leads_masked = leads.withColumns(
    {
        "cpf_masked": F.transform("cpfs", mask_cpf_udf),
        "cpf_hash": F.transform("cpfs", hash_udf),
        "email_masked": F.transform("emails", mask_email_udf),
        "phone_masked": F.transform("phones", mask_phone_udf),
        "plate_masked": F.transform("plates", mask_plate_udf),
    }
).drop("cpfs", "emails", "phones", "plates")

# ============================================================
# 5. REDACTION DO MESSAGE_BODY em messages_clean
# ============================================================
df_redacted = df.withColumn("message_body", redact_udf("message_body"))

# Sobrescrever messages_clean com message_body redacted (UC)
(
    df_redacted.write.format("delta")
    .mode("overwrite")
    .option("mergeSchema", "true")
    .saveAsTable(SILVER_MESSAGES)
)

# Upload messages_clean redacted para S3
msg_tmp = lake.make_temp_dir("silver_msg_redacted_")
local_msg = f"{msg_tmp}/messages_clean"
df_redacted.write.format("delta").mode("overwrite").option("mergeSchema", "true").save(local_msg)
n_msg = lake.upload_dir(local_msg, "silver/messages_clean/")
logger.info(f"Delta uploaded para S3 silver/messages_clean/ (redacted): {n_msg} arquivos")

# ============================================================
# 6. SALVAR LEADS PROFILE (UC + S3)
# ============================================================
(
    leads_masked.write.format("delta")
    .mode("overwrite")
    .option("mergeSchema", "true")
    .saveAsTable(SILVER_LEADS)
)

# Upload leads_profile para S3
leads_tmp = lake.make_temp_dir("silver_leads_")
local_leads = f"{leads_tmp}/leads_profile"
leads_masked.write.format("delta").mode("overwrite").option("mergeSchema", "true").save(local_leads)
n_leads = lake.upload_dir(local_leads, "silver/leads_profile/")
logger.info(f"Delta uploaded para S3 silver/leads_profile/: {n_leads} arquivos")

leads_count = spark.table(SILVER_LEADS).count()
duration = round(time.time() - start_time, 2)

logger.info(f"Silver leads_profile: {leads_count} leads em {duration}s")

try:
    dbutils.jobs.taskValues.set(key="status", value="SUCCESS")
    dbutils.jobs.taskValues.set(key="rows_output", value=leads_count)
    dbutils.jobs.taskValues.set(key="duration_sec", value=duration)
except Exception:
    pass

dbutils.notebook.exit(f"SUCCESS: {leads_count} leads profiled, message_body redacted, {duration}s")
