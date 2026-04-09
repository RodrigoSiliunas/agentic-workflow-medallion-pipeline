# Databricks notebook source
# MAGIC %md
# MAGIC # Gold: Sentiment Analysis (ML — pysentimiento)
# MAGIC Upgrade da heuristica para modelo BERT pre-treinado em pt-BR.
# MAGIC
# MAGIC **Pre-requisito**: instalar no cluster:
# MAGIC ```
# MAGIC %pip install pysentimiento
# MAGIC ```

# COMMAND ----------

# MAGIC %pip install pysentimiento

# COMMAND ----------

import logging
import sys
import time

from pyspark.sql import functions as F
from pyspark.sql.types import FloatType, StringType

logger = logging.getLogger("gold.sentiment_ml")

sys.path.insert(0, "/Workspace/Repos/rodrigosiliunas1@gmail.com/agentic-workflow-medallion-pipeline/pipeline")
from pipeline_lib.storage import S3Lake

lake = S3Lake(dbutils)
CATALOG = "medallion"
start_time = time.time()

messages = spark.table(f"{CATALOG}.silver.messages_clean")

# COMMAND ----------

# ============================================================
# 1. CRIAR MODELO DE SENTIMENTO (broadcast para workers)
# ============================================================
from pysentimiento import create_analyzer

analyzer = create_analyzer(task="sentiment", lang="pt")

# Broadcast do analyzer para os workers
analyzer_bc = spark.sparkContext.broadcast(analyzer)

# COMMAND ----------

# ============================================================
# 2. PANDAS UDF PARA SENTIMENTO
# ============================================================
import pandas as pd


@F.pandas_udf(FloatType())
def sentiment_score_udf(texts: pd.Series) -> pd.Series:
    """Calcula sentimento via pysentimiento. Retorna score -1.0 a +1.0."""
    model = analyzer_bc.value
    scores = []
    for text in texts:
        if not text or not isinstance(text, str) or len(text.strip()) < 3:
            scores.append(0.0)
            continue
        try:
            result = model.predict(text[:512])  # Limitar a 512 tokens
            # pysentimiento retorna probas para POS, NEG, NEU
            pos = result.probas.get("POS", 0)
            neg = result.probas.get("NEG", 0)
            scores.append(round(pos - neg, 3))
        except Exception:
            scores.append(0.0)
    return pd.Series(scores)


@F.pandas_udf(StringType())
def sentiment_label_udf(texts: pd.Series) -> pd.Series:
    """Retorna label: positivo, negativo, neutro."""
    model = analyzer_bc.value
    labels = []
    for text in texts:
        if not text or not isinstance(text, str) or len(text.strip()) < 3:
            labels.append("neutro")
            continue
        try:
            result = model.predict(text[:512])
            label_map = {"POS": "positivo", "NEG": "negativo", "NEU": "neutro"}
            labels.append(label_map.get(result.output, "neutro"))
        except Exception:
            labels.append("neutro")
    return pd.Series(labels)

# COMMAND ----------

# ============================================================
# 3. APLICAR SENTIMENTO NAS MENSAGENS INBOUND
# ============================================================
inbound = messages.filter(
    (F.col("direction") == "inbound")
    & (F.col("message_body").isNotNull())
    & (F.col("message_body") != "")
)

msg_sentiment = inbound.withColumns(
    {
        "ml_sentiment_score": sentiment_score_udf("message_body"),
        "ml_sentiment_label": sentiment_label_udf("message_body"),
    }
)

# COMMAND ----------

# ============================================================
# 4. AGREGAR POR CONVERSA
# ============================================================
conv_sentiment = msg_sentiment.groupBy("conversation_id").agg(
    F.avg("ml_sentiment_score").alias("sentiment_score"),
    F.count("*").alias("inbound_messages"),
    F.sum(F.when(F.col("ml_sentiment_label") == "positivo", 1).otherwise(0)).alias(
        "positive_count"
    ),
    F.sum(F.when(F.col("ml_sentiment_label") == "negativo", 1).otherwise(0)).alias(
        "negative_count"
    ),
    F.first("conversation_outcome").alias("outcome"),
)

conv_sentiment = conv_sentiment.withColumn(
    "sentiment_label",
    F.when(F.col("sentiment_score") > 0.2, "positivo")
    .when(F.col("sentiment_score") < -0.2, "negativo")
    .otherwise("neutro"),
).withColumn("model_version", F.lit("pysentimiento_bert_pt"))

# COMMAND ----------

# ============================================================
# 5. SALVAR (sobrescreve a tabela de sentimento heuristico)
# ============================================================
GOLD_TABLE = f"{CATALOG}.gold.sentiment"
conv_sentiment.write.format("delta").mode("overwrite").option("mergeSchema", "true").saveAsTable(
    GOLD_TABLE
)

# Upload para S3
tmp = lake.make_temp_dir("gold_sentiment_ml_")
local_path = f"{tmp}/sentiment"
conv_sentiment.write.format("delta").mode("overwrite").option("mergeSchema", "true").save(local_path)
lake.upload_dir(local_path, "gold/sentiment/")

duration = round(time.time() - start_time, 2)
count = conv_sentiment.count()
logger.info(f"Gold sentiment (ML): {count} conversas em {duration}s")
dbutils.notebook.exit(f"SUCCESS: {count} conversations, ML model, {duration}s")
