# Databricks notebook source
# MAGIC %md
# MAGIC # Gold: Analytics Orchestrator
# MAGIC Executa todos os notebooks Gold na ordem correta de dependencias.
# MAGIC Cada notebook e executado via `dbutils.notebook.run()` com timeout de 10 min.
# MAGIC
# MAGIC **Camada:** Gold (orquestrador) | **Dependencia:** todas as tabelas Silver
# MAGIC **Output:** todas as tabelas Gold (funil, agent_performance, sentiment, etc.)
# MAGIC
# MAGIC _Ultima atualizacao: 2026-04-09_

# COMMAND ----------

# DBTITLE 1,Imports e Setup
import logging
import time

logger = logging.getLogger("gold.analytics")
start_time = time.time()

# COMMAND ----------

# DBTITLE 1,Parametros
dbutils.widgets.text("catalog", "medallion", "Catalog Name")
dbutils.widgets.text("scope", "medallion-pipeline", "Secret Scope")

CATALOG = dbutils.widgets.get("catalog")
SCOPE = dbutils.widgets.get("scope")

# COMMAND ----------

# DBTITLE 1,Executar Notebooks na Ordem de Dependencias
# Auto-detect repo path for sub-notebook calls
_nb_path = dbutils.notebook.entry_point.getDbutils().notebook().getContext().notebookPath().get()
_repo_root = "/".join(_nb_path.split("/")[:4])
NOTEBOOK_BASE = f"{_repo_root}/pipelines/pipeline-seguradora-whatsapp/notebooks"

TIMEOUT = 600  # 10 min por notebook

# Fases organizadas por dependência:
# Notebooks dentro da mesma fase rodam em PARALELO (ThreadPoolExecutor).
# Fases rodam em SEQUÊNCIA (phase 2 depende de phase 1).
from concurrent.futures import ThreadPoolExecutor, as_completed

phases = [
    # Phase 1: Core (sem dependências entre si)
    {
        "name": "Core",
        "notebooks": [
            ("funnel", f"{NOTEBOOK_BASE}/gold/funnel"),
            ("agent_performance", f"{NOTEBOOK_BASE}/gold/agent_performance"),
            ("sentiment", f"{NOTEBOOK_BASE}/gold/sentiment"),
            ("email_providers", f"{NOTEBOOK_BASE}/gold/email_providers"),
        ],
    },
    # Phase 2: Depende de sentiment (phase 1)
    {
        "name": "Scoring + Analytics",
        "notebooks": [
            ("lead_scoring", f"{NOTEBOOK_BASE}/gold/lead_scoring"),
            ("temporal_analysis", f"{NOTEBOOK_BASE}/gold/temporal_analysis"),
            ("competitor_intel", f"{NOTEBOOK_BASE}/gold/competitor_intel"),
        ],
    },
    # Phase 3: Depende de lead_scoring (phase 2)
    {
        "name": "Avançado",
        "notebooks": [
            ("campaign_roi", f"{NOTEBOOK_BASE}/gold/campaign_roi"),
            ("segmentation", f"{NOTEBOOK_BASE}/gold/segmentation"),
            ("churn_reengagement", f"{NOTEBOOK_BASE}/gold/churn_reengagement"),
            ("negotiation_complexity", f"{NOTEBOOK_BASE}/gold/negotiation_complexity"),
            ("first_contact_resolution", f"{NOTEBOOK_BASE}/gold/first_contact_resolution"),
        ],
    },
]

results = {}
errors = []

def run_notebook(name_path):
    """Executa um notebook e retorna (nome, resultado_ou_erro)."""
    name, path = name_path
    try:
        result = dbutils.notebook.run(path, TIMEOUT)
        return (name, result)
    except Exception as e:
        return (name, f"FAILED: {e}")

# Executa fases sequencialmente, notebooks dentro de cada fase em paralelo
for phase in phases:
    phase_name = phase["name"]
    nbs = phase["notebooks"]
    logger.info(f"Phase: {phase_name} ({len(nbs)} notebooks em paralelo)")

    with ThreadPoolExecutor(max_workers=len(nbs)) as executor:
        futures = {executor.submit(run_notebook, nb): nb[0] for nb in nbs}
        for future in as_completed(futures):
            name, result = future.result()
            results[name] = result
            if result.startswith("FAILED"):
                errors.append(f"{name} falhou: {result}")
                logger.error(f"  FALHOU: {name}")
            else:
                logger.info(f"  OK: {name}")

# COMMAND ----------

# DBTITLE 1,Resumo da Execucao
# Calcula estatisticas de sucesso/falha (total = soma de notebooks de todas as fases)
total = sum(len(phase["notebooks"]) for phase in phases)
succeeded = sum(1 for v in results.values() if v.startswith("SUCCESS"))
failed = total - succeeded

duration = round(time.time() - start_time, 2)

summary = f"{succeeded}/{total} notebooks OK, {failed} falhas, {duration}s"
logger.info(summary)

# Seta task values (disponiveis para o Observer em caso de falha)
try:
    dbutils.jobs.taskValues.set(key="status", value="SUCCESS" if failed == 0 else "PARTIAL")
    dbutils.jobs.taskValues.set(key="succeeded", value=succeeded)
    dbutils.jobs.taskValues.set(key="failed", value=failed)
    dbutils.jobs.taskValues.set(key="duration_sec", value=duration)
    dbutils.jobs.taskValues.set(key="errors", value=str(errors) if errors else "none")
except Exception:
    pass

if failed > 0:
    dbutils.notebook.exit(f"PARTIAL: {summary}\nErrors: {errors}")
else:
    dbutils.notebook.exit(f"SUCCESS: {summary}")
