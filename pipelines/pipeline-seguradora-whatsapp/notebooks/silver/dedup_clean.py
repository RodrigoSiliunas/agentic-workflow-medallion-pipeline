# Databricks notebook source
# MAGIC %md
# MAGIC # Silver Task 2a: Dedup + Clean + Metadata Parse
# MAGIC Deduplicacao de mensagens sent+delivered (mantendo a de maior prioridade),
# MAGIC normalizacao de sender_name, e parse de campos JSON do metadata em colunas tipadas.
# MAGIC
# MAGIC **Camada:** Silver | **Dependencia:** bronze.conversations | **Output:** `silver.messages_clean`
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
PIPELINE_ROOT = f"/Workspace{_repo_root}/pipelines/pipeline-seguradora-whatsapp"
sys.path.insert(0, PIPELINE_ROOT)

from pipeline_lib.storage import S3Lake
from pipeline_lib.validation import delta_row_count

# COMMAND ----------

# DBTITLE 1,Parametros
dbutils.widgets.text("catalog", "medallion", "Catalog Name")
dbutils.widgets.text("scope", "medallion-pipeline", "Secret Scope")

CATALOG = dbutils.widgets.get("catalog")
SCOPE = dbutils.widgets.get("scope")

# Inicializa lake client e logger
lake = S3Lake(dbutils, spark, scope=SCOPE)
logger = logging.getLogger("silver.dedup_clean")

# COMMAND ----------

# DBTITLE 1,Configuracao de Tabelas
chaos_mode = dbutils.widgets.get("chaos_mode")
# Tabela de entrada (Bronze) e saida (Silver)
BRONZE_TABLE = f"{CATALOG}.bronze.conversations"
SILVER_TABLE = f"{CATALOG}.silver.messages_clean"

# Marca inicio para medir duracao
start_time = time.time()

# COMMAND ----------

# DBTITLE 1,Ler Bronze
df = spark.table(BRONZE_TABLE)
# T5: usa Delta metadata — sem full scan pre-dedup
bronze_count = delta_row_count(spark, BRONZE_TABLE)
logger.info(f"Bronze: {bronze_count} linhas")

# CHAOS: Injeta NULLs no conversation_id que quebram o dedup/groupBy
if chaos_mode == "silver_null":
    logger.warning("CHAOS MODE: Injetando NULLs em conversation_id")
    try:
        dbutils.jobs.taskValues.set(key="status", value="FAILED")
        dbutils.jobs.taskValues.set(
            key="error",
            value="NullPointerException em conversation_id durante dedup"
        )
    except Exception:
        pass
    raise ValueError(
        "CHAOS: conversation_id contem NULLs — injetado pelo "
        "chaos mode para teste do agente AI"
    )

# COMMAND ----------

# DBTITLE 1,Deduplicacao
# Prioridade de status: read > delivered > sent
# Quando ha duplicatas (mesma conversa, timestamp, direcao, sender e body),
# mantemos apenas a com maior prioridade de status
status_priority = (
    F.when(F.col("status") == "read", 3)
    .when(F.col("status") == "delivered", 2)
    .otherwise(1)
)

# Window para ranking dentro de cada grupo de duplicatas
w = Window.partitionBy(
    "conversation_id", "timestamp", "direction", "sender_phone", "message_body"
).orderBy(status_priority.desc())

# Mantem apenas o registro de maior prioridade (rank 1)
df_dedup = df.withColumn("_rank", F.row_number().over(w)).filter(F.col("_rank") == 1).drop("_rank")

# T5: nao conta df_dedup aqui (força full scan duplicado do plan de dedup).
# A contagem vem do metadata Delta apos o write, sem custo adicional.

# COMMAND ----------

# DBTITLE 1,Normalizacao de sender_name
# Trata nomes nulos/vazios e normaliza formatacao:
# - Outbound sem nome: usa agent_id como fallback
# - Inbound sem nome: gera nome placeholder com ultimos 8 chars do conversation_id
# - Nomes validos: trim, remove espacos duplos, aplica InitCap
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

# COMMAND ----------

# DBTITLE 1,Parse Metadata JSON
# Extrai campos do JSON metadata em colunas tipadas para facilitar queries downstream
# Campos: device, city, state, response_time_sec, is_business_hours, lead_source
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

# COMMAND ----------

# DBTITLE 1,Salvar como Delta Table e Upload para S3
# Salva com merge de schema para aceitar colunas novas (schema evolution)
(
    df_parsed.write.format("delta")
    .mode("overwrite")
    .option("mergeSchema", "true")
    .saveAsTable(SILVER_TABLE)
)

# T5: row count via Delta metadata (O(1)) em vez de count() pos-write.
silver_count = delta_row_count(spark, SILVER_TABLE)
removed = bronze_count - silver_count

# Backup em Parquet no S3
lake.write_parquet(df_parsed, "silver/messages_clean/")
logger.info("Parquet uploaded para S3 silver/messages_clean/")

duration = round(time.time() - start_time, 2)
logger.info(f"Silver messages_clean: {silver_count} linhas em {duration}s ({removed} dedup removidas)")

# COMMAND ----------

# DBTITLE 1,Metricas e Task Values
# Seta task values (disponiveis para o Observer em caso de falha)
try:
    dbutils.jobs.taskValues.set(key="status", value="SUCCESS")
    dbutils.jobs.taskValues.set(key="rows_input", value=bronze_count)
    dbutils.jobs.taskValues.set(key="rows_output", value=silver_count)
    dbutils.jobs.taskValues.set(key="rows_removed", value=removed)
    dbutils.jobs.taskValues.set(key="duration_sec", value=duration)
except Exception:
    pass

dbutils.notebook.exit(f"SUCCESS: {silver_count} rows, {removed} dedup removed, {duration}s")
