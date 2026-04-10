# Databricks notebook source
# MAGIC %md
# MAGIC # Gold: Negotiation Complexity
# MAGIC Analisa a correlacao entre numero e tipo de perguntas feitas pelo lead
# MAGIC e o outcome da conversa. Tipos: perguntas de preco e perguntas de cobertura.
# MAGIC
# MAGIC **Camada:** Gold | **Dependencia:** silver.messages_clean
# MAGIC **Output:** `gold.negotiation_complexity`, `gold.negotiation_by_outcome`
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
logger = logging.getLogger("gold.negotiation_complexity")
start_time = time.time()

# COMMAND ----------

# DBTITLE 1,Carregar Mensagens
messages = spark.table(f"{CATALOG}.silver.messages_clean")

# COMMAND ----------

# DBTITLE 1,Contar e Classificar Perguntas por Conversa
# Filtra mensagens inbound com texto para analise de perguntas
inbound = messages.filter(
    (F.col("direction") == "inbound") & (F.col("message_body").isNotNull())
)

# Classifica cada mensagem: se e pergunta, se e sobre preco, se e sobre cobertura
questions = inbound.withColumn(
    # Qualquer mensagem com "?" e considerada pergunta
    "is_question", F.col("message_body").contains("?").cast("int")
).withColumn(
    # Perguntas sobre preco/valor/desconto
    "is_price_question",
    F.when(
        F.col("message_body").rlike("(?i)(preco|valor|custa|parcela|desconto|barato|caro)"),
        1,
    ).otherwise(0),
).withColumn(
    # Perguntas sobre cobertura/assistencia
    "is_coverage_question",
    F.when(
        F.col("message_body").rlike("(?i)(cobertura|cobre|inclui|protege|assistencia|guincho)"),
        1,
    ).otherwise(0),
)

# Agrega por conversa: total de perguntas, por tipo, e taxa de perguntas
complexity = questions.groupBy("conversation_id").agg(
    F.sum("is_question").alias("total_questions"),
    F.sum("is_price_question").alias("price_questions"),
    F.sum("is_coverage_question").alias("coverage_questions"),
    F.count("*").alias("total_inbound_messages"),
    F.first("conversation_outcome").alias("outcome"),
)

# Taxa de perguntas: proporcao de mensagens que sao perguntas
complexity = complexity.withColumn(
    "question_rate", F.round(F.col("total_questions") / F.col("total_inbound_messages"), 3)
)

# COMMAND ----------

# DBTITLE 1,Correlacao Perguntas vs Outcome
# Media de perguntas (total, preco, cobertura) por outcome
# Permite identificar se perguntar mais sobre preco correlaciona com perda
by_outcome = complexity.groupBy("outcome").agg(
    F.avg("total_questions").alias("avg_questions"),
    F.avg("price_questions").alias("avg_price_questions"),
    F.avg("coverage_questions").alias("avg_coverage_questions"),
    F.avg("question_rate").alias("avg_question_rate"),
    F.count("*").alias("conversations"),
)

# COMMAND ----------

# DBTITLE 1,Salvar no Unity Catalog e S3
# Tabela detalhada por conversa
complexity.write.format("delta").mode("overwrite").option("mergeSchema", "true").saveAsTable(
    f"{CATALOG}.gold.negotiation_complexity"
)

# Tabela resumo por outcome
by_outcome.write.format("delta").mode("overwrite").saveAsTable(
    f"{CATALOG}.gold.negotiation_by_outcome"
)

# Backup em Parquet no S3
lake.write_parquet(complexity, "gold/negotiation_complexity/")
lake.write_parquet(by_outcome, "gold/negotiation_by_outcome/")

duration = round(time.time() - start_time, 2)
logger.info(f"Gold negotiation_complexity em {duration}s")
dbutils.notebook.exit(f"SUCCESS in {duration}s")
