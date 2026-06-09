# Databricks notebook source
# MAGIC %md
# MAGIC # Quality Validation
# MAGIC Verifica integridade de todas as camadas Bronze -> Silver -> Gold apos cada
# MAGIC execucao do pipeline. Checa contagem de linhas, presenca de PII em texto claro,
# MAGIC colunas obrigatorias, range de scores, e existencia de tabelas Gold.
# MAGIC
# MAGIC **Camada:** Validacao | **Dependencia:** todas as tabelas do pipeline
# MAGIC **Output:** task values com status PASS/FAIL, lista de erros e warnings
# MAGIC
# MAGIC _Ultima atualizacao: 2026-04-09_

# COMMAND ----------

# DBTITLE 1,Imports e Setup
import logging
import re
import sys
import time

from pyspark.sql import functions as F

# Auto-detect repo path para importar pipeline_lib
_nb_path = (
    dbutils.notebook.entry_point.getDbutils().notebook().getContext().notebookPath().get()
)
_repo_root = "/".join(_nb_path.split("/")[:4])
PIPELINE_ROOT = f"/Workspace{_repo_root}/pipelines/pipeline-seguradora-whatsapp"
sys.path.insert(0, PIPELINE_ROOT)

from pipeline_lib.validation import delta_row_count

logger = logging.getLogger("validation.checks")

# COMMAND ----------

# DBTITLE 1,Parametros
dbutils.widgets.text("catalog", "medallion", "Catalog Name")

CATALOG = dbutils.widgets.get("catalog")

# COMMAND ----------

# DBTITLE 1,Chaos Mode Check
chaos_mode = dbutils.widgets.get("chaos_mode")

# Inicializa contadores de tempo, erros e warnings
start_time = time.time()
errors = []
warnings = []

# CHAOS: Injeta erro de validacao impossivel de passar
if chaos_mode == "validation_strict":
    logger.warning("CHAOS MODE: Injetando validacao impossivel")
    errors.append(
        "CHAOS: Threshold impossivel — Silver deve ter exatamente "
        "o mesmo numero de linhas que Bronze (sem dedup)"
    )
    try:
        dbutils.jobs.taskValues.set(key="status", value="FAIL")
        dbutils.jobs.taskValues.set(
            key="error",
            value="CHAOS: Validacao com threshold impossivel injetada"
        )
    except Exception:
        pass

# COMMAND ----------

# DBTITLE 1,Bronze Checks
# Verifica se a tabela Bronze existe e tem dados (via Delta metadata — O(1))
try:
    bronze_count = delta_row_count(spark, f"{CATALOG}.bronze.conversations")

    if bronze_count == 0:
        errors.append("Bronze vazia (0 linhas)")
    else:
        logger.info(f"Bronze: {bronze_count} linhas OK")
except Exception as e:
    errors.append(f"Bronze nao existe ou erro: {e}")
    bronze_count = 0

# COMMAND ----------

# DBTITLE 1,Silver Checks
# Verifica messages_clean: contagem, dedup, e PII residual
#
# NOTA sobre threshold Silver/Bronze:
# O Bronze acumula dados ao longo de varias runs (append/overwrite cumulativo),
# enquanto o Silver eh reconstruido a partir do snapshot atual de mensagens unicas
# apos dedup agressivo (sent+delivered colapsam). Por isso, a razao Silver/Bronze
# tende a cair naturalmente conforme o pipeline executa mais vezes — isso NAO
# indica perda de dados.
#
# Mantemos um threshold critico bem baixo (1%) apenas para capturar colapsos
# catastroficos do Silver, e validamos saude absoluta (>1000 linhas) como sinal
# primario de que o Silver esta operacional.
try:
    messages = spark.table(f"{CATALOG}.silver.messages_clean")
    messages_count = delta_row_count(spark, f"{CATALOG}.silver.messages_clean")

    # Se Silver tem mais linhas que Bronze, dedup pode nao ter funcionado
    if bronze_count > 0 and messages_count >= bronze_count:
        warnings.append(
            f"Silver messages_clean ({messages_count}) >= Bronze ({bronze_count}). "
            "Dedup nao removeu linhas?"
        )

    # Sanity check absoluto: Silver precisa ter um volume minimo de dados.
    # Isso eh mais confiavel que razao Silver/Bronze, ja que o Bronze cresce a
    # cada run mas o Silver representa o snapshot atual deduplicado.
    MIN_SILVER_ROWS = 1000
    if messages_count < MIN_SILVER_ROWS:
        errors.append(
            f"Silver messages_clean com volume criticamente baixo: "
            f"{messages_count} linhas (minimo esperado: {MIN_SILVER_ROWS})"
        )

    # Threshold critico: apenas se Silver colapsou para <1% do Bronze.
    # Como Bronze acumula runs, razoes baixas sao esperadas e nao indicam bug.
    if bronze_count > 0 and messages_count < bronze_count * 0.01:
        errors.append(
            f"Silver com menos de 1% do Bronze: {messages_count}/{bronze_count} "
            "(possivel colapso do pipeline Silver)"
        )
    elif bronze_count > 0 and messages_count < bronze_count * 0.03:
        warnings.append(
            f"Silver com menos de 3% do Bronze: {messages_count}/{bronze_count} "
            "(esperado se Bronze acumulou muitas runs ou dedup foi agressivo)"
        )

    # Verifica que message_body nao contem PII em texto claro (CPF)
    # Amostra 500 mensagens para nao sobrecarregar o cluster
    CPF_PATTERN = r"\b\d{3}\.\d{3}\.\d{3}-\d{2}\b"
    sample = messages.select("message_body").limit(500).collect()
    pii_found = 0
    for row in sample:
        if row.message_body and re.search(CPF_PATTERN, str(row.message_body)):
            pii_found += 1

    if pii_found > 0:
        errors.append(f"PII detectado em {pii_found} mensagens da Silver (CPF em texto claro)")

    logger.info(f"Silver messages_clean: {messages_count} linhas")
except Exception as e:
    errors.append(f"Silver messages_clean nao existe: {e}")

# Verifica leads_profile: existencia e colunas de mascaramento obrigatorias
try:
    leads = spark.table(f"{CATALOG}.silver.leads_profile")
    leads_count = delta_row_count(spark, f"{CATALOG}.silver.leads_profile")
    logger.info(f"Silver leads_profile: {leads_count} leads")

    # Colunas de mascaramento sao obrigatorias -- sem elas, PII pode vazar
    lead_cols = set(leads.columns)
    expected = {"cpf_masked", "email_masked", "phone_masked", "plate_masked"}
    missing = expected - lead_cols
    if missing:
        errors.append(f"Silver leads_profile faltando colunas: {missing}")
except Exception as e:
    errors.append(f"Silver leads_profile nao existe: {e}")

# Verifica conversations_enriched: existencia basica
try:
    convs_count = delta_row_count(
        spark, f"{CATALOG}.silver.conversations_enriched"
    )
    logger.info(f"Silver conversations_enriched: {convs_count} conversas")
except Exception as e:
    errors.append(f"Silver conversations_enriched nao existe: {e}")

# COMMAND ----------

# DBTITLE 1,Gold Checks
# Verifica existencia e dados de todas as tabelas Gold
gold_tables = [
    "agent_performance", "campaign_geo", "campaign_roi", "churn_reengagement",
    "competitor_intel", "email_providers", "fcr_summary", "first_contact_resolution",
    "lead_scoring", "negotiation_by_outcome", "negotiation_complexity",
    "persona_summary", "personas", "sentiment", "temporal_analysis",
]

for table_name in gold_tables:
    full_name = f"{CATALOG}.gold.{table_name}"
    try:
        # T5: Delta metadata no lugar de count() — O(1) em vez de O(n).
        count = delta_row_count(spark, full_name)
        if count == 0:
            warnings.append(f"Gold {table_name} vazia (0 linhas)")
        else:
            logger.info(f"Gold {table_name}: {count} linhas OK")
    except Exception as e:
        errors.append(f"Gold {table_name} nao existe: {e}")

# Verifica range do lead_score (deve ser 0-100)
# T5: single agg pra min+max — antes eram duas passadas.
try:
    scores_agg = (
        spark.table(f"{CATALOG}.gold.lead_scoring")
        .agg(F.min("lead_score").alias("mn"), F.max("lead_score").alias("mx"))
        .first()
    )
    min_score, max_score = scores_agg["mn"], scores_agg["mx"]
    if min_score is not None and (min_score < 0 or max_score > 100):
        errors.append(f"Lead scores fora do range 0-100: min={min_score}, max={max_score}")
except Exception:
    pass

# Verifica range do sentiment_score (deve ser -1.0 a +1.0)
try:
    sent_agg = (
        spark.table(f"{CATALOG}.gold.sentiment")
        .agg(F.min("sentiment_score").alias("mn"), F.max("sentiment_score").alias("mx"))
        .first()
    )
    min_s, max_s = sent_agg["mn"], sent_agg["mx"]
    if min_s is not None and (min_s < -1.0 or max_s > 1.0):
        errors.append(f"Sentiment fora do range -1/+1: min={min_s}, max={max_s}")
except Exception:
    pass

# COMMAND ----------

# DBTITLE 1,Resultado Final da Validacao
duration = round(time.time() - start_time, 2)
# PASS se nenhum erro critico; FAIL se houver qualquer erro
status = "PASS" if len(errors) == 0 else "FAIL"

result = {
    "status": status,
    "errors": errors,
    "warnings": warnings,
    "duration_sec": duration,
}

logger.info(f"Validation: {status} ({len(errors)} errors, {len(warnings)} warnings) em {duration}s")

# Seta task values (disponiveis para o Observer em caso de falha)
try:
    dbutils.jobs.taskValues.set(key="status", value=status)
    dbutils.jobs.taskValues.set(key="errors", value=str(errors) if errors else "none")
    dbutils.jobs.taskValues.set(key="warnings", value=str(warnings) if warnings else "none")
except Exception:
    pass

if errors:
    raise ValueError(f"FAIL: {len(errors)} errors: {errors}")
else:
    dbutils.notebook.exit(f"PASS: {len(warnings)} warnings in {duration}s")
