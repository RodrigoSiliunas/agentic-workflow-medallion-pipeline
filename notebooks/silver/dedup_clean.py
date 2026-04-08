# Databricks notebook source
# MAGIC %md
# MAGIC # Silver Task 2a: Dedup + Clean + Metadata Parse
# MAGIC Deduplicacao sent+delivered, normalizacao de nomes, parse de metadata JSON.

import logging
import time

from pyspark.sql import Window
from pyspark.sql import functions as F

logger = logging.getLogger("silver.dedup_clean")

# ============================================================
# TASK VALUES DO AGENTE
# ============================================================
try:
    should_process = dbutils.jobs.taskValues.get(
        taskKey="agent_pre", key="should_process", default=True
    )
    if not should_process:
        dbutils.notebook.exit("SKIP")
    run_id = dbutils.jobs.taskValues.get(taskKey="agent_pre", key="run_id", default="standalone")
except Exception:
    run_id = "standalone"

# ============================================================
# CONFIGURACAO
# ============================================================
CATALOG = spark.conf.get("pipeline.catalog", "medallion")
BRONZE_TABLE = f"{CATALOG}.bronze.conversations"
SILVER_TABLE = f"{CATALOG}.silver.messages_clean"

start_time = time.time()

# ============================================================
# 1. LER BRONZE
# ============================================================
df = spark.table(BRONZE_TABLE)
bronze_count = df.count()
logger.info(f"Bronze: {bronze_count} linhas")

# ============================================================
# 2. DEDUPLICACAO (sent + delivered -> manter status mais avancado)
# ============================================================
status_priority = (
    F.when(F.col("status") == "read", 3)
    .when(F.col("status") == "delivered", 2)
    .otherwise(1)
)

w = Window.partitionBy(
    "conversation_id", "timestamp", "direction", "sender_phone", "message_body"
).orderBy(status_priority.desc())

df_dedup = df.withColumn("_rank", F.row_number().over(w)).filter(F.col("_rank") == 1).drop("_rank")

dedup_count = df_dedup.count()
removed = bronze_count - dedup_count
logger.info(f"Dedup: {removed} duplicatas removidas. {dedup_count} linhas restantes.")

# ============================================================
# 3. NORMALIZACAO DE sender_name
# ============================================================
df_clean = df_dedup.withColumn(
    "sender_name_normalized",
    F.when(
        (F.col("sender_name").isNull()) | (F.trim(F.col("sender_name")) == ""),
        F.when(
            F.col("direction") == "outbound",
            F.col("agent_id"),
        ).otherwise(F.concat(F.lit("Lead_"), F.substring(F.col("conversation_id"), -8, 8))),
    ).otherwise(F.initcap(F.trim(F.regexp_replace(F.col("sender_name"), r"\s+", " ")))),
)

# ============================================================
# 4. PARSE METADATA JSON
# ============================================================
df_parsed = df_clean.withColumns(
    {
        "meta_device": F.get_json_object("metadata", "$.device"),
        "meta_city": F.get_json_object("metadata", "$.city"),
        "meta_state": F.get_json_object("metadata", "$.state"),
        "meta_response_time_sec": F.get_json_object("metadata", "$.response_time_sec").cast(
            "int"
        ),
        "meta_is_business_hours": F.get_json_object("metadata", "$.is_business_hours").cast(
            "boolean"
        ),
        "meta_lead_source": F.get_json_object("metadata", "$.lead_source"),
    }
)

# ============================================================
# 5. SALVAR COMO DELTA TABLE
# ============================================================
(
    df_parsed.write.format("delta")
    .mode("overwrite")
    .option("mergeSchema", "true")
    .saveAsTable(SILVER_TABLE)
)

silver_count = spark.table(SILVER_TABLE).count()
duration = round(time.time() - start_time, 2)

logger.info(f"Silver messages_clean: {silver_count} linhas em {duration}s")

# ============================================================
# 6. METRICAS
# ============================================================
try:
    dbutils.jobs.taskValues.set(key="status", value="SUCCESS")
    dbutils.jobs.taskValues.set(key="rows_input", value=bronze_count)
    dbutils.jobs.taskValues.set(key="rows_output", value=silver_count)
    dbutils.jobs.taskValues.set(key="rows_removed", value=removed)
    dbutils.jobs.taskValues.set(key="duration_sec", value=duration)
except Exception:
    pass

dbutils.notebook.exit(f"SUCCESS: {silver_count} rows, {removed} dedup removed, {duration}s")
