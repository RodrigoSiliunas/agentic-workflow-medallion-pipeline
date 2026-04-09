# Databricks notebook source
# MAGIC %md
# MAGIC # Gold: Persona Segmentation
# MAGIC Classifica leads em 6 personas comportamentais baseadas em engajamento,
# MAGIC outcome, sentimento, dados fornecidos e mencao a concorrentes.
# MAGIC Personas: decidido_rapido, comparador_preco, engajado_indeciso, ghost, lead_quente, curioso.
# MAGIC
# MAGIC **Camada:** Gold | **Dependencia:** silver.conversations_enriched, gold.sentiment, gold.lead_scoring, silver.leads_profile
# MAGIC **Output:** `gold.personas`, `gold.persona_summary`
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
_repo_root = "/".join(_nb_path.split("/")[:5])
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
logger = logging.getLogger("gold.segmentation")
start_time = time.time()

# COMMAND ----------

# DBTITLE 1,Carregar Tabelas de Dependencia
# Combina 4 fontes de dados para features de segmentacao
conversations = spark.table(f"{CATALOG}.silver.conversations_enriched")
sentiment = spark.table(f"{CATALOG}.gold.sentiment")
lead_scores = spark.table(f"{CATALOG}.gold.lead_scoring")
leads = spark.table(f"{CATALOG}.silver.leads_profile")

# COMMAND ----------

# DBTITLE 1,Combinar Features de Todas as Fontes
# Join de conversas + sentimento + score + entidades para montar o perfil completo
combined = (
    conversations.join(sentiment.select("conversation_id", "sentiment_score"), on="conversation_id")
    .join(lead_scores.select("conversation_id", "lead_score"), on="conversation_id")
    .join(
        leads.select(
            "conversation_id",
            # Conta dados fornecidos e concorrentes mencionados
            F.size("cpf_masked").alias("provided_cpf"),
            F.size("email_masked").alias("provided_email"),
            F.size("plate_masked").alias("provided_plate"),
            F.size("competitors_mentioned").alias("mentioned_competitors"),
        ),
        on="conversation_id",
        how="left",
    )
)

# COMMAND ----------

# DBTITLE 1,Classificacao em 6 Personas
# Regras de classificacao (aplicadas em ordem de prioridade):
# 1. decidido_rapido: poucas mensagens + venda fechada
# 2. comparador_preco: mencionou concorrente + perdido por preco/concorrente
# 3. engajado_indeciso: muitas mensagens + ainda em negociacao
# 4. ghost: poucos inbound + ghosting
# 5. lead_quente: forneceu CPF + sentimento positivo
# 6. curioso: desistencia propria
personas = combined.withColumn(
    "persona",
    F.when(
        (F.col("total_messages") <= 5) & (F.col("outcome") == "venda_fechada"),
        "decidido_rapido",
    )
    .when(
        (F.col("mentioned_competitors") > 0)
        & F.col("outcome").isin("perdido_preco", "perdido_concorrente"),
        "comparador_preco",
    )
    .when(
        (F.col("total_messages") >= 15)
        & F.col("outcome").isin("em_negociacao", "proposta_enviada"),
        "engajado_indeciso",
    )
    .when(
        (F.col("inbound_count") <= 3) & (F.col("outcome") == "ghosting"),
        "ghost",
    )
    .when(
        (F.col("provided_cpf") > 0) & (F.col("sentiment_score") > 0),
        "lead_quente",
    )
    .when(
        (F.col("outcome") == "desistencia_lead"),
        "curioso",
    )
    .otherwise("indefinido"),
)

# COMMAND ----------

# DBTITLE 1,Resumo Estatistico por Persona
# Metricas medias por persona para entender o perfil de cada grupo
persona_summary = personas.groupBy("persona").agg(
    F.count("*").alias("total"),
    F.avg("lead_score").alias("avg_lead_score"),
    F.avg("sentiment_score").alias("avg_sentiment"),
    F.avg("total_messages").alias("avg_messages"),
    F.avg("avg_response_time_sec").alias("avg_response_time"),
)

# COMMAND ----------

# DBTITLE 1,Salvar no Unity Catalog e S3
# Tabela principal com persona por conversa
personas_result = personas.select(
    "conversation_id", "persona", "outcome", "lead_score", "sentiment_score",
    "total_messages", "campaign_id", "agent_id",
)
personas_result.write.format("delta").mode("overwrite").option("mergeSchema", "true").saveAsTable(
    f"{CATALOG}.gold.personas"
)

# Tabela de resumo por persona
persona_summary.write.format("delta").mode("overwrite").saveAsTable(
    f"{CATALOG}.gold.persona_summary"
)

# Backup em Parquet no S3
lake.write_parquet(personas_result, "gold/personas/")
lake.write_parquet(persona_summary, "gold/persona_summary/")

duration = round(time.time() - start_time, 2)
logger.info(f"Gold personas em {duration}s")
dbutils.notebook.exit(f"SUCCESS in {duration}s")
