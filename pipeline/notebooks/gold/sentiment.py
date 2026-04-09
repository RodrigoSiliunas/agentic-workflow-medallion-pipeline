# Databricks notebook source
# MAGIC %md
# MAGIC # Gold: Sentiment Analysis (Heuristica pt-BR)
# MAGIC Sentimento por conversa baseado em keywords positivas/negativas.

# COMMAND ----------

import logging
import sys
import time

from pyspark.sql import functions as F

logger = logging.getLogger("gold.sentiment")

sys.path.insert(0, "/Workspace/Repos/rodrigosiliunas1@gmail.com/agentic-workflow-medallion-pipeline/pipeline")
from pipeline_lib.storage import S3Lake

lake = S3Lake(dbutils, spark)
CATALOG = "medallion"
start_time = time.time()

messages = spark.table(f"{CATALOG}.silver.messages_clean")

# COMMAND ----------

# ============================================================
# KEYWORDS DE SENTIMENTO (pt-BR informal, WhatsApp)
# ============================================================
POSITIVE = [
    "otimo", "perfeito", "excelente", "maravilha", "fechado", "aceito",
    "pode fazer", "vamos fechar", "gostei", "muito bom", "top",
    "obrigado", "obrigada", "show", "massa", "sensacional",
    "tranquilo", "beleza", "ok vamos", "sim aceito", "quero sim",
    "confianca", "seguranca", "tranquilidade", "protecao",
]

NEGATIVE = [
    "caro", "muito caro", "absurdo", "nao quero", "desisto",
    "nao tenho interesse", "vou pensar", "ta ruim", "pessimo",
    "nao gostei", "cancelar", "reclamar", "demora", "demorado",
    "nao vale", "melhor nao", "sem condicao", "fora do orcamento",
    "concorrente", "mais barato", "preco alto", "nao compensa",
]

# COMMAND ----------

# ============================================================
# 1. CALCULAR SENTIMENTO POR MENSAGEM INBOUND
# ============================================================
positive_pattern = "|".join(POSITIVE)
negative_pattern = "|".join(NEGATIVE)

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

# ============================================================
# 2. AGREGAR POR CONVERSA
# ============================================================
conv_sentiment = msg_sentiment.groupBy("conversation_id").agg(
    F.sum("positive_hits").alias("total_positive"),
    F.sum("negative_hits").alias("total_negative"),
    F.count("*").alias("inbound_messages"),
    F.first("conversation_outcome").alias("outcome"),
)

# Score: -1.0 (muito negativo) a +1.0 (muito positivo)
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
    "sentiment_label",
    F.when(F.col("sentiment_score") > 0.2, "positivo")
    .when(F.col("sentiment_score") < -0.2, "negativo")
    .otherwise("neutro"),
)

# COMMAND ----------

# ============================================================
# 3. SALVAR
# ============================================================
GOLD_TABLE = f"{CATALOG}.gold.sentiment"
conv_sentiment.write.format("delta").mode("overwrite").option("mergeSchema", "true").saveAsTable(
    GOLD_TABLE
)

# Upload para S3 (in-memory)
lake.write_parquet(conv_sentiment, "gold/sentiment/")

duration = round(time.time() - start_time, 2)
count = conv_sentiment.count()
logger.info(f"Gold sentiment: {count} conversas em {duration}s")
dbutils.notebook.exit(f"SUCCESS: {count} conversations scored in {duration}s")
