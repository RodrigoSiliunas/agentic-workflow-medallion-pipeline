# Databricks notebook source
# MAGIC %md
# MAGIC # Gold: Outcome Prediction
# MAGIC Modelo simples (Logistic Regression) que preve conversation_outcome usando
# MAGIC apenas features das primeiras 3 mensagens. Objetivo: prever outcome cedo
# MAGIC para priorizar leads com maior probabilidade de conversao.
# MAGIC
# MAGIC **Pre-requisito**: scikit-learn instalado via `%pip install`
# MAGIC
# MAGIC **Camada:** Gold | **Dependencia:** silver.messages_clean, silver.conversations_enriched
# MAGIC **Output:** `gold.outcome_prediction`, `gold.model_metrics`
# MAGIC
# MAGIC _Ultima atualizacao: 2026-04-09_

# COMMAND ----------

# DBTITLE 1,Instalar Dependencia ML
# scikit-learn para modelo de classificacao
# MAGIC %pip install scikit-learn

# COMMAND ----------

# DBTITLE 1,Imports e Setup
import json
import logging
import os
import sys
import time

import numpy as np
from pyspark.sql import Window
from pyspark.sql import functions as F
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, classification_report
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import LabelEncoder

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
logger = logging.getLogger("gold.outcome_prediction")
start_time = time.time()

# COMMAND ----------

# DBTITLE 1,Carregar Tabelas Silver
messages = spark.table(f"{CATALOG}.silver.messages_clean")
conversations = spark.table(f"{CATALOG}.silver.conversations_enriched")

# COMMAND ----------

# DBTITLE 1,Extrair Features das Primeiras 3 Mensagens
# Limita a analise as primeiras 3 mensagens de cada conversa
# Objetivo: features que estao disponiveis cedo para predicao em tempo real
w = Window.partitionBy("conversation_id").orderBy("timestamp")
first_msgs = messages.withColumn("msg_num", F.row_number().over(w)).filter(F.col("msg_num") <= 3)

# Agrega features das primeiras 3 mensagens por conversa
early_features = first_msgs.groupBy("conversation_id").agg(
    F.hour(F.min("timestamp")).alias("contact_hour"),          # Hora do primeiro contato
    F.dayofweek(F.min("timestamp")).alias("contact_dow"),      # Dia da semana
    F.avg(F.length("message_body")).alias("avg_msg_length"),   # Tamanho medio das mensagens
    F.sum(F.when(F.col("direction") == "inbound", 1).otherwise(0)).alias("early_inbound_count"),
    F.sum(
        F.when(F.col("message_body").contains("?"), 1).otherwise(0)
    ).alias("early_questions"),                                 # Perguntas nas primeiras msgs
    F.first("meta_response_time_sec").alias("first_response_time"),
    F.first("meta_is_business_hours").cast("int").alias("is_business_hours"),
)

# Join com conversas para pegar outcome (target) e features adicionais
features = early_features.join(
    conversations.select("conversation_id", "outcome", "lead_source", "device"),
    on="conversation_id",
)

# COMMAND ----------

# DBTITLE 1,Preparar Dados para scikit-learn
# Converte para Pandas e codifica features categoricas com LabelEncoder
pdf = features.toPandas()

le_source = LabelEncoder()
le_device = LabelEncoder()
le_outcome = LabelEncoder()

# Encode de variaveis categoricas, tratando nulls como "unknown"
pdf["lead_source_enc"] = le_source.fit_transform(pdf["lead_source"].fillna("unknown"))
pdf["device_enc"] = le_device.fit_transform(pdf["device"].fillna("unknown"))
pdf["outcome_enc"] = le_outcome.fit_transform(pdf["outcome"])

# Features numericas usadas para treino
feature_cols = [
    "contact_hour", "contact_dow", "avg_msg_length", "early_inbound_count",
    "early_questions", "first_response_time", "is_business_hours",
    "lead_source_enc", "device_enc",
]

X = pdf[feature_cols].fillna(0).values
y = pdf["outcome_enc"].values

# COMMAND ----------

# DBTITLE 1,Treinar Modelo de Logistic Regression
# Split 80/20 com seed fixa para reprodutibilidade
X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

# Logistic Regression multinomial (multiplas classes de outcome)
model = LogisticRegression(max_iter=1000, multi_class="multinomial", random_state=42)
model.fit(X_train, y_train)

# Avaliacao no set de teste
y_pred = model.predict(X_test)
accuracy = accuracy_score(y_test, y_pred)
report = classification_report(y_test, y_pred, target_names=le_outcome.classes_, output_dict=True)

logger.info(f"Accuracy: {accuracy:.3f}")

# COMMAND ----------

# DBTITLE 1,Salvar Predicoes e Metricas do Modelo
# Gera predicoes para todo o dataset
pdf["predicted_outcome"] = le_outcome.inverse_transform(model.predict(X))
pdf["prediction_proba_max"] = np.max(model.predict_proba(X), axis=1)

# Converte resultado de volta para Spark DataFrame
result_df = spark.createDataFrame(
    pdf[["conversation_id", "outcome", "predicted_outcome", "prediction_proba_max"]]
)

# Adiciona flag de acerto, versao do modelo e accuracy global
result_df = result_df.withColumns(
    {
        "correct": (F.col("outcome") == F.col("predicted_outcome")).cast("int"),
        "model_version": F.lit("logistic_regression_v1"),
        "model_accuracy": F.lit(round(accuracy, 3)),
    }
)

# Salva predicoes no Unity Catalog
GOLD_TABLE = f"{CATALOG}.gold.outcome_prediction"
result_df.write.format("delta").mode("overwrite").option("mergeSchema", "true").saveAsTable(
    GOLD_TABLE
)

# Salva metricas do modelo para tracking de performance ao longo do tempo
metrics_row = spark.createDataFrame(
    [
        {
            "model": "logistic_regression_v1",
            "accuracy": round(accuracy, 3),
            "features": json.dumps(feature_cols),
            "train_size": len(X_train),
            "test_size": len(X_test),
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
        }
    ]
)
# Append para manter historico de metricas
metrics_row.write.format("delta").mode("append").saveAsTable(
    f"{CATALOG}.gold.model_metrics"
)

# Backup em Parquet no S3
lake.write_parquet(result_df, "gold/outcome_prediction/")
lake.write_parquet(metrics_row, "gold/model_metrics/")

duration = round(time.time() - start_time, 2)
logger.info(f"Gold outcome_prediction: accuracy={accuracy:.3f} em {duration}s")
dbutils.notebook.exit(f"SUCCESS: accuracy={accuracy:.3f}, {len(pdf)} predictions in {duration}s")
