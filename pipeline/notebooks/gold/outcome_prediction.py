# Databricks notebook source
# MAGIC %md
# MAGIC # Gold: Outcome Prediction
# MAGIC Modelo simples (Logistic Regression) que preve conversation_outcome
# MAGIC usando apenas features das primeiras 3 mensagens.

# COMMAND ----------

# MAGIC %pip install scikit-learn

# COMMAND ----------

dbutils.widgets.text("catalog", "medallion", "Catalog Name")
dbutils.widgets.text("scope", "medallion-pipeline", "Secret Scope")

CATALOG = dbutils.widgets.get("catalog")
SCOPE = dbutils.widgets.get("scope")

# COMMAND ----------

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
_repo_root = "/".join(_nb_path.split("/")[:5])
PIPELINE_ROOT = f"/Workspace{_repo_root}/pipeline"
sys.path.insert(0, PIPELINE_ROOT)

from pipeline_lib.storage import S3Lake

lake = S3Lake(dbutils, spark, scope=SCOPE)
logger = logging.getLogger("gold.outcome_prediction")
start_time = time.time()

messages = spark.table(f"{CATALOG}.silver.messages_clean")
conversations = spark.table(f"{CATALOG}.silver.conversations_enriched")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Extrair Features das Primeiras 3 Mensagens

# COMMAND ----------

w = Window.partitionBy("conversation_id").orderBy("timestamp")
first_msgs = messages.withColumn("msg_num", F.row_number().over(w)).filter(F.col("msg_num") <= 3)

early_features = first_msgs.groupBy("conversation_id").agg(
    F.hour(F.min("timestamp")).alias("contact_hour"),
    F.dayofweek(F.min("timestamp")).alias("contact_dow"),
    F.avg(F.length("message_body")).alias("avg_msg_length"),
    F.sum(F.when(F.col("direction") == "inbound", 1).otherwise(0)).alias("early_inbound_count"),
    F.sum(
        F.when(F.col("message_body").contains("?"), 1).otherwise(0)
    ).alias("early_questions"),
    F.first("meta_response_time_sec").alias("first_response_time"),
    F.first("meta_is_business_hours").cast("int").alias("is_business_hours"),
)

features = early_features.join(
    conversations.select("conversation_id", "outcome", "lead_source", "device"),
    on="conversation_id",
)

# COMMAND ----------

# MAGIC %md
# MAGIC ## Preparar Dados para sklearn

# COMMAND ----------

pdf = features.toPandas()

le_source = LabelEncoder()
le_device = LabelEncoder()
le_outcome = LabelEncoder()

pdf["lead_source_enc"] = le_source.fit_transform(pdf["lead_source"].fillna("unknown"))
pdf["device_enc"] = le_device.fit_transform(pdf["device"].fillna("unknown"))
pdf["outcome_enc"] = le_outcome.fit_transform(pdf["outcome"])

feature_cols = [
    "contact_hour", "contact_dow", "avg_msg_length", "early_inbound_count",
    "early_questions", "first_response_time", "is_business_hours",
    "lead_source_enc", "device_enc",
]

X = pdf[feature_cols].fillna(0).values
y = pdf["outcome_enc"].values

# COMMAND ----------

# MAGIC %md
# MAGIC ## Treinar Modelo

# COMMAND ----------

X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

model = LogisticRegression(max_iter=1000, multi_class="multinomial", random_state=42)
model.fit(X_train, y_train)

y_pred = model.predict(X_test)
accuracy = accuracy_score(y_test, y_pred)
report = classification_report(y_test, y_pred, target_names=le_outcome.classes_, output_dict=True)

logger.info(f"Accuracy: {accuracy:.3f}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Salvar Predicoes + Metricas

# COMMAND ----------

import json

pdf["predicted_outcome"] = le_outcome.inverse_transform(model.predict(X))
pdf["prediction_proba_max"] = np.max(model.predict_proba(X), axis=1)

result_df = spark.createDataFrame(
    pdf[["conversation_id", "outcome", "predicted_outcome", "prediction_proba_max"]]
)

result_df = result_df.withColumns(
    {
        "correct": (F.col("outcome") == F.col("predicted_outcome")).cast("int"),
        "model_version": F.lit("logistic_regression_v1"),
        "model_accuracy": F.lit(round(accuracy, 3)),
    }
)

GOLD_TABLE = f"{CATALOG}.gold.outcome_prediction"
result_df.write.format("delta").mode("overwrite").option("mergeSchema", "true").saveAsTable(
    GOLD_TABLE
)

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
metrics_row.write.format("delta").mode("append").saveAsTable(
    f"{CATALOG}.gold.model_metrics"
)

lake.write_parquet(result_df, "gold/outcome_prediction/")
lake.write_parquet(metrics_row, "gold/model_metrics/")

duration = round(time.time() - start_time, 2)
logger.info(f"Gold outcome_prediction: accuracy={accuracy:.3f} em {duration}s")
dbutils.notebook.exit(f"SUCCESS: accuracy={accuracy:.3f}, {len(pdf)} predictions in {duration}s")
