# Databricks notebook source
# MAGIC %md
# MAGIC # Gold: Sentiment Analysis (ML -- pysentimiento)
# MAGIC Upgrade da heuristica para modelo BERT pre-treinado em pt-BR (pysentimiento).
# MAGIC Usa Pandas UDFs para inferencia distribuida nos workers do cluster.
# MAGIC Sobrescreve a tabela gold.sentiment com scores do modelo ML.
# MAGIC
# MAGIC **Pre-requisito**: pysentimiento instalado via `%pip install`
# MAGIC
# MAGIC **Camada:** Gold | **Dependencia:** silver.messages_clean
# MAGIC **Output:** `gold.sentiment` (sobrescreve tabela heuristica)
# MAGIC
# MAGIC _Ultima atualizacao: 2026-04-09_

# COMMAND ----------

# DBTITLE 1,Instalar Dependencia ML
# pysentimiento: modelo BERT pre-treinado para sentimento em pt-BR
# MAGIC %pip install pysentimiento

# COMMAND ----------

# DBTITLE 1,Imports e Setup
import logging
import os
import sys
import time

from pyspark.sql import functions as F
from pyspark.sql.types import FloatType, StringType

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
logger = logging.getLogger("gold.sentiment_ml")
start_time = time.time()

# COMMAND ----------

# DBTITLE 1,Carregar Mensagens
messages = spark.table(f"{CATALOG}.silver.messages_clean")

# COMMAND ----------

# DBTITLE 1,Criar Modelo de Sentimento (broadcast para workers)
# Inicializa o analyzer de sentimento do pysentimiento
# Usa modelo BERT fine-tuned para portugues
from pysentimiento import create_analyzer

analyzer = create_analyzer(task="sentiment", lang="pt")

# Broadcast do modelo para todos os workers do cluster
# Evita serializar o modelo a cada task -- envia uma vez e reutiliza
analyzer_bc = spark.sparkContext.broadcast(analyzer)

# COMMAND ----------

# DBTITLE 1,Pandas UDFs para Sentimento
import pandas as pd


@F.pandas_udf(FloatType())
def sentiment_score_udf(texts: pd.Series) -> pd.Series:
    """Calcula sentimento via pysentimiento. Retorna score -1.0 a +1.0.
    Textos curtos ou nulos recebem score 0.0 (neutro)."""
    model = analyzer_bc.value
    scores = []
    for text in texts:
        # Ignora textos nulos, nao-string ou muito curtos
        if not text or not isinstance(text, str) or len(text.strip()) < 3:
            scores.append(0.0)
            continue
        try:
            # Trunca em 512 chars (limite do BERT)
            result = model.predict(text[:512])
            pos = result.probas.get("POS", 0)
            neg = result.probas.get("NEG", 0)
            scores.append(round(pos - neg, 3))
        except Exception:
            scores.append(0.0)
    return pd.Series(scores)


@F.pandas_udf(StringType())
def sentiment_label_udf(texts: pd.Series) -> pd.Series:
    """Retorna label categorico: positivo, negativo, neutro."""
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

# DBTITLE 1,Aplicar Sentimento nas Mensagens Inbound
# Filtra mensagens inbound com texto nao vazio
inbound = messages.filter(
    (F.col("direction") == "inbound")
    & (F.col("message_body").isNotNull())
    & (F.col("message_body") != "")
)

# Aplica ambas as UDFs (score e label) em uma unica passada
msg_sentiment = inbound.withColumns(
    {
        "ml_sentiment_score": sentiment_score_udf("message_body"),
        "ml_sentiment_label": sentiment_label_udf("message_body"),
    }
)

# COMMAND ----------

# DBTITLE 1,Agregar por Conversa
# Calcula score medio e contagem de positivos/negativos por conversa
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

# Label categorico e versao do modelo para rastreabilidade
conv_sentiment = conv_sentiment.withColumn(
    "sentiment_label",
    F.when(F.col("sentiment_score") > 0.2, "positivo")
    .when(F.col("sentiment_score") < -0.2, "negativo")
    .otherwise("neutro"),
).withColumn("model_version", F.lit("pysentimiento_bert_pt"))

# COMMAND ----------

# DBTITLE 1,Salvar (sobrescreve tabela de sentimento heuristico)
GOLD_TABLE = f"{CATALOG}.gold.sentiment"
conv_sentiment.write.format("delta").mode("overwrite").option("mergeSchema", "true").saveAsTable(
    GOLD_TABLE
)

# Backup em Parquet no S3
lake.write_parquet(conv_sentiment, "gold/sentiment/")

duration = round(time.time() - start_time, 2)
count = conv_sentiment.count()
logger.info(f"Gold sentiment (ML): {count} conversas em {duration}s")
dbutils.notebook.exit(f"SUCCESS: {count} conversations, ML model, {duration}s")
