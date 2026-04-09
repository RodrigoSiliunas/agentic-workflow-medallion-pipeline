# Databricks notebook source
# MAGIC %md
# MAGIC # Silver Task 2b: Entity Extraction + Masking + Redaction
# MAGIC Extrai entidades (CPF, email, phone, plate, vehicle, CEP, competitor, price)
# MAGIC das mensagens inbound, mascara dados sensiveis com format-preserving encryption,
# MAGIC e aplica redaction no message_body para remover PII em texto claro.
# MAGIC
# MAGIC **Camada:** Silver | **Dependencia:** silver.messages_clean
# MAGIC **Output:** `silver.leads_profile` (entidades mascaradas) + `silver.messages_clean` (redacted)
# MAGIC
# MAGIC _Ultima atualizacao: 2026-04-09_

# COMMAND ----------

# DBTITLE 1,Imports e Setup
import logging
import os
import sys
import time

from pyspark.sql import functions as F
from pyspark.sql.types import ArrayType, FloatType, StringType

# Auto-detect repo path from this notebook's location
_nb_path = dbutils.notebook.entry_point.getDbutils().notebook().getContext().notebookPath().get()
_repo_root = "/".join(_nb_path.split("/")[:4])
PIPELINE_ROOT = f"/Workspace{_repo_root}/pipeline"
sys.path.insert(0, PIPELINE_ROOT)

from pipeline_lib.storage import S3Lake
from pipeline_lib.extractors import competitor, cpf, cep, email, phone, plate, price, vehicle

# COMMAND ----------

# DBTITLE 1,Parametros
dbutils.widgets.text("catalog", "medallion", "Catalog Name")
dbutils.widgets.text("scope", "medallion-pipeline", "Secret Scope")

CATALOG = dbutils.widgets.get("catalog")
SCOPE = dbutils.widgets.get("scope")

# Inicializa lake client e logger
lake = S3Lake(dbutils, spark, scope=SCOPE)
logger = logging.getLogger("silver.entities_mask")

# COMMAND ----------

# DBTITLE 1,Verificar Task Values do Agente
# Verifica se o agent_pre autorizou o processamento
try:
    should_process = dbutils.jobs.taskValues.get(
        taskKey="agent_pre", key="should_process", default=True
    )
    if not should_process:
        dbutils.notebook.exit("SKIP")
except Exception:
    pass

# COMMAND ----------

# DBTITLE 1,Carregar MASKING_SECRET e Funcoes de Masking
# MASKING_SECRET e a chave usada para format-preserving encryption dos dados sensiveis
# Armazenada no Databricks Secrets para nao ficar em texto claro no codigo
os.environ["MASKING_SECRET"] = dbutils.secrets.get(SCOPE, "masking-secret")

# Importa funcoes de mascaramento apos definir a variavel de ambiente
from pipeline_lib.masking.format_preserving import mask_cpf, mask_email, mask_phone, mask_plate
from pipeline_lib.masking.hash_based import hash_value
from pipeline_lib.masking.redaction import redact_message_body

# COMMAND ----------

# DBTITLE 1,Configuracao de Tabelas
# Tabelas de entrada (messages_clean) e saida (leads_profile)
SILVER_MESSAGES = f"{CATALOG}.silver.messages_clean"
SILVER_LEADS = f"{CATALOG}.silver.leads_profile"

# Marca inicio para medir duracao total
start_time = time.time()

# COMMAND ----------

# DBTITLE 1,Registrar UDFs de Extracao e Mascaramento
# UDFs de extracao: recebem message_body e retornam array de entidades encontradas
extract_cpf_udf = F.udf(cpf.extract, ArrayType(StringType()))
extract_email_udf = F.udf(email.extract, ArrayType(StringType()))
extract_phone_udf = F.udf(phone.extract, ArrayType(StringType()))
extract_plate_udf = F.udf(plate.extract, ArrayType(StringType()))
extract_cep_udf = F.udf(cep.extract, ArrayType(StringType()))
extract_competitor_udf = F.udf(competitor.extract, ArrayType(StringType()))
extract_price_udf = F.udf(price.extract, ArrayType(FloatType()))

# UDFs de mascaramento: format-preserving para manter formato legivel
mask_cpf_udf = F.udf(mask_cpf, StringType())
mask_email_udf = F.udf(mask_email, StringType())
mask_phone_udf = F.udf(mask_phone, StringType())
mask_plate_udf = F.udf(mask_plate, StringType())
# Hash HMAC irreversivel para CPFs (usado como chave de join segura)
hash_udf = F.udf(hash_value, StringType())
# Redaction: substitui PII no texto por placeholders como [CPF_REDACTED]
redact_udf = F.udf(redact_message_body, StringType())

# COMMAND ----------

# DBTITLE 1,Ler Messages Clean (inbound com texto)
df = spark.table(SILVER_MESSAGES)
# Filtra apenas mensagens inbound com corpo de texto nao vazio
# (entidades so sao extraidas do que o lead envia)
df_inbound = df.filter(
    (F.col("direction") == "inbound")
    & (F.col("message_body").isNotNull())
    & (F.col("message_body") != "")
)

# COMMAND ----------

# DBTITLE 1,Extrair Entidades das Mensagens
# Aplica todos os extractors via UDFs em uma unica passada
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

# COMMAND ----------

# DBTITLE 1,Agregar por Conversa para Leads Profile
# Agrupa entidades por conversation_id para criar o perfil do lead
# flatten + collect_set: desaninha arrays e remove duplicatas
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

# COMMAND ----------

# DBTITLE 1,Mascarar Dados Sensiveis
# Converte para Pandas para aplicar mascaramento item-a-item
# (UDFs de masking operam em strings individuais, nao em arrays)
import pandas as pd

leads_rows = leads.collect()
leads_pdf = pd.DataFrame([r.asDict() for r in leads_rows])

def safe_map(arr, fn):
    """Aplica funcao a cada elemento do array, tratando None/vazio."""
    return [fn(x) for x in (arr or [])] if arr else []

# Aplica mascaramento format-preserving e hash HMAC
leads_pdf["cpf_masked"] = leads_pdf["cpfs"].apply(lambda a: safe_map(a, mask_cpf))
leads_pdf["cpf_hash"] = leads_pdf["cpfs"].apply(lambda a: safe_map(a, hash_value))
leads_pdf["email_masked"] = leads_pdf["emails"].apply(lambda a: safe_map(a, mask_email))
leads_pdf["phone_masked"] = leads_pdf["phones"].apply(lambda a: safe_map(a, mask_phone))
leads_pdf["plate_masked"] = leads_pdf["plates"].apply(lambda a: safe_map(a, mask_plate))

# Remove colunas com dados em texto claro (PII)
leads_pdf = leads_pdf.drop(columns=["cpfs", "emails", "phones", "plates"])

# Schema explicito para evitar NullType em arrays vazios
from pyspark.sql.types import StructType, StructField, LongType

array_str = ArrayType(StringType())
array_float = ArrayType(FloatType())
schema = StructType([
    StructField("conversation_id", StringType()),
    StructField("ceps", array_str),
    StructField("competitors_mentioned", array_str),
    StructField("prices_mentioned", array_float),
    StructField("lead_name", StringType()),
    StructField("lead_phone", StringType()),
    StructField("cpf_masked", array_str),
    StructField("cpf_hash", array_str),
    StructField("email_masked", array_str),
    StructField("phone_masked", array_str),
    StructField("plate_masked", array_str),
])
leads_masked = spark.createDataFrame(leads_pdf, schema=schema)

# COMMAND ----------

# DBTITLE 1,Redaction do message_body
# Aplica redaction em TODAS as mensagens (inbound e outbound)
# para remover qualquer PII que apareca no texto
df_redacted = df.withColumn("message_body", redact_udf("message_body"))

# Sobrescreve a tabela messages_clean com a versao redacted
(
    df_redacted.write.format("delta")
    .mode("overwrite")
    .option("mergeSchema", "true")
    .saveAsTable(SILVER_MESSAGES)
)

lake.write_parquet(spark.table(SILVER_MESSAGES), "silver/messages_clean/")
logger.info("Parquet uploaded para S3 silver/messages_clean/ (redacted)")

# COMMAND ----------

# DBTITLE 1,Salvar Leads Profile
# Persiste o perfil de cada lead com entidades mascaradas
(
    leads_masked.write.format("delta")
    .mode("overwrite")
    .option("mergeSchema", "true")
    .saveAsTable(SILVER_LEADS)
)

lake.write_parquet(spark.table(SILVER_LEADS), "silver/leads_profile/")
logger.info("Parquet uploaded para S3 silver/leads_profile/")

# Metricas finais
leads_count = spark.table(SILVER_LEADS).count()
duration = round(time.time() - start_time, 2)

logger.info(f"Silver leads_profile: {leads_count} leads em {duration}s")

# Seta task values para o agent_post
try:
    dbutils.jobs.taskValues.set(key="status", value="SUCCESS")
    dbutils.jobs.taskValues.set(key="rows_output", value=leads_count)
    dbutils.jobs.taskValues.set(key="duration_sec", value=duration)
except Exception:
    pass

dbutils.notebook.exit(f"SUCCESS: {leads_count} leads profiled, message_body redacted, {duration}s")
