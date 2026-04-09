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
import time

from pyspark.sql import functions as F

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
# Verifica se a tabela Bronze existe e tem dados
try:
    bronze = spark.table(f"{CATALOG}.bronze.conversations")
    bronze_count = bronze.count()

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
try:
    messages = spark.table(f"{CATALOG}.silver.messages_clean")
    messages_count = messages.count()

    # Se Silver tem mais linhas que Bronze, dedup pode nao ter funcionado
    if bronze_count > 0 and messages_count >= bronze_count:
        warnings.append(
            f"Silver messages_clean ({messages_count}) >= Bronze ({bronze_count}). "
            "Dedup nao removeu linhas?"
        )

    # Verifica que dedup nao removeu linhas demais.
    # O bronze acumula runs (overwrite), e o dedup remove duplicados sent+delivered,
    # entao a reducao pode ser significativa (~50-85% eh normal).
    # Alerta se Silver tem MENOS de 5% do Bronze (algo drastico aconteceu).
    if bronze_count > 0 and messages_count < bronze_count * 0.05:
        errors.append(
            f"Silver perdeu mais de 95% das linhas: {messages_count}/{bronze_count}"
        )
    elif bronze_count > 0 and messages_count < bronze_count * 0.10:
        warnings.append(
            f"Silver com menos de 10% do Bronze: {messages_count}/{bronze_count} "
            "(pode ser normal se dedup removeu muitos duplicados)"
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
    leads_count = leads.count()
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
    convs = spark.table(f"{CATALOG}.silver.conversations_enriched")
    convs_count = convs.count()
    logger.info(f"Silver conversations_enriched: {convs_count} conversas")
except Exception as e:
    errors.append(f"Silver conversations_enriched nao existe: {e}")

# COMMAND ----------

# DBTITLE 1,Gold Checks
# Verifica existencia e dados de todas as tabelas Gold
gold_tables = [
    "funil_vendas", "agent_performance", "sentiment", "lead_scoring",
    "email_providers", "temporal_analysis", "competitor_intel", "campaign_roi",
    "personas", "churn_reengagement", "negotiation_complexity",
    "first_contact_resolution",
]

for table_name in gold_tables:
    full_name = f"{CATALOG}.gold.{table_name}"
    try:
        count = spark.table(full_name).count()
        if count == 0:
            warnings.append(f"Gold {table_name} vazia (0 linhas)")
        else:
            logger.info(f"Gold {table_name}: {count} linhas OK")
    except Exception as e:
        errors.append(f"Gold {table_name} nao existe: {e}")

# Verifica range do lead_score (deve ser 0-100)
try:
    scores = spark.table(f"{CATALOG}.gold.lead_scoring")
    min_score = scores.agg(F.min("lead_score")).first()[0]
    max_score = scores.agg(F.max("lead_score")).first()[0]
    if min_score is not None and (min_score < 0 or max_score > 100):
        errors.append(f"Lead scores fora do range 0-100: min={min_score}, max={max_score}")
except Exception:
    pass

# Verifica range do sentiment_score (deve ser -1.0 a +1.0)
try:
    sent = spark.table(f"{CATALOG}.gold.sentiment")
    min_s = sent.agg(F.min("sentiment_score")).first()[0]
    max_s = sent.agg(F.max("sentiment_score")).first()[0]
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

# Seta task values para o agent_post coletar
try:
    dbutils.jobs.taskValues.set(key="status", value=status)
    dbutils.jobs.taskValues.set(key="errors", value=str(errors) if errors else "none")
    dbutils.jobs.taskValues.set(key="warnings", value=str(warnings) if warnings else "none")
except Exception:
    pass

if errors:
    dbutils.notebook.exit(f"FAIL: {len(errors)} errors: {errors}")
else:
    dbutils.notebook.exit(f"PASS: {len(warnings)} warnings in {duration}s")
