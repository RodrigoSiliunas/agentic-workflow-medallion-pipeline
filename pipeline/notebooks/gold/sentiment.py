# Databricks notebook source
# MAGIC %md
# MAGIC # Gold: Sentiment Analysis (Heuristica pt-BR)
# MAGIC Analise de sentimento por conversa baseada em keywords positivas/negativas
# MAGIC do portugues informal usado em WhatsApp. Score normalizado de -1 a +1.
# MAGIC
# MAGIC **Camada:** Gold | **Dependencia:** silver.messages_clean
# MAGIC **Output:** `gold.sentiment`
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
PIPELINE_ROOT = f"/Workspace{_repo_root}/pipeline"
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
logger = logging.getLogger("gold.sentiment")
start_time = time.time()

# COMMAND ----------

# DBTITLE 1,Carregar Mensagens
messages = spark.table(f"{CATALOG}.silver.messages_clean")

# COMMAND ----------

# DBTITLE 1,Keywords de Sentimento (pt-BR informal WhatsApp)
# Keywords positivas: indicam interesse, satisfacao, decisao de compra
POSITIVE = [
    "otimo", "perfeito", "excelente", "maravilha", "fechado", "aceito",
    "pode fazer", "vamos fechar", "gostei", "muito bom", "top",
    "obrigado", "obrigada", "show", "massa", "sensacional",
    "tranquilo", "beleza", "ok vamos", "sim aceito", "quero sim",
    "confianca", "seguranca", "tranquilidade", "protecao",
]

# Keywords negativas: indicam insatisfacao, desistencia, objecao de preco
NEGATIVE = [
    "caro", "muito caro", "absurdo", "nao quero", "desisto",
    "nao tenho interesse", "vou pensar", "ta ruim", "pessimo",
    "nao gostei", "cancelar", "reclamar", "demora", "demorado",
    "nao vale", "melhor nao", "sem condicao", "fora do orcamento",
    "concorrente", "mais barato", "preco alto", "nao compensa",
]

# COMMAND ----------

# DBTITLE 1,Calcular Sentimento por Mensagem Inbound
# Monta regex patterns a partir das listas de keywords
positive_pattern = "|".join(POSITIVE)
negative_pattern = "|".join(NEGATIVE)

# Conta hits positivos e negativos em cada mensagem inbound com texto
msg_sentiment = messages.filter(
    (F.col("direction") == "inbound") & (F.col("message_body").isNotNull())
).withColumns(
    {
        "positive_hits": F.size(
            F.expr(f"filter(split(lower(message_body), ' '), x -> x rlike '{positive_pattern}')")
        ),
        "negative_hits": F.size(
            F.expr(f"filter(split(lower(message_body), ' '), x -> x rlike '{negative_pattern}')")
        ),
    }
)

# COMMAND ----------

# DBTITLE 1,Agregar por Conversa
# Soma hits positivos e negativos por conversa e calcula score normalizado
conv_sentiment = msg_sentiment.groupBy("conversation_id").agg(
    F.sum("positive_hits").alias("total_positive"),
    F.sum("negative_hits").alias("total_negative"),
    F.count("*").alias("inbound_messages"),
    F.first("conversation_outcome").alias("outcome"),
)

# Score normalizado: (pos - neg) / (pos + neg), range -1 a +1
# Quando nao ha hits, score = 0 (neutro)
conv_sentiment = conv_sentiment.withColumn(
    "sentiment_score",
    F.when(
        (F.col("total_positive") + F.col("total_negative")) == 0,
        F.lit(0.0),
    ).otherwise(
        F.round(
            (F.col("total_positive") - F.col("total_negative"))
            / (F.col("total_positive") + F.col("total_negative")),
            3,
        )
    ),
).withColumn(
    # Label categorico baseado em thresholds de +/- 0.2
    "sentiment_label",
    F.when(F.col("sentiment_score") > 0.2, "positivo")
    .when(F.col("sentiment_score") < -0.2, "negativo")
    .otherwise("neutro"),
)

# COMMAND ----------

# DBTITLE 1,Salvar no Unity Catalog e S3
GOLD_TABLE = f"{CATALOG}.gold.sentiment"
conv_sentiment.write.format("delta").mode("overwrite").option("mergeSchema", "true").saveAsTable(
    GOLD_TABLE
)

# Backup em Parquet no S3
lake.write_parquet(conv_sentiment, "gold/sentiment/")

duration = round(time.time() - start_time, 2)
count = conv_sentiment.count()
logger.info(f"Gold sentiment: {count} conversas em {duration}s")
dbutils.notebook.exit(f"SUCCESS: {count} conversations scored in {duration}s")
