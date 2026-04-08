# Databricks notebook source
# MAGIC %md
# MAGIC # Agent Post-Check (Task 5)
# MAGIC Verifica resultados, recovery com rollback Delta, notificacoes por email.
# MAGIC **run_if: ALL_DONE** — roda SEMPRE, mesmo se tasks anteriores falharam.

import json
import logging
import time
from datetime import datetime

from pyspark.sql import Row

logger = logging.getLogger("agent_post")

# ============================================================
# CONFIGURACAO
# ============================================================
CATALOG = spark.conf.get("pipeline.catalog", "medallion")
STATE_TABLE = f"{CATALOG}.pipeline.state"
NOTIFICATIONS_TABLE = f"{CATALOG}.pipeline.notifications"
METRICS_TABLE = f"{CATALOG}.pipeline.metrics"
MAX_CONSECUTIVE_FAILURES = 3

# ============================================================
# 1. CRIAR TABELAS DE APOIO (se nao existirem)
# ============================================================
spark.sql(f"""
    CREATE TABLE IF NOT EXISTS {NOTIFICATIONS_TABLE} (
        timestamp    STRING,
        level        STRING,
        subject      STRING,
        body         STRING,
        run_id       STRING
    ) USING DELTA
""")

spark.sql(f"""
    CREATE TABLE IF NOT EXISTS {METRICS_TABLE} (
        task         STRING,
        run_id       STRING,
        timestamp    STRING,
        rows_input   LONG,
        rows_output  LONG,
        rows_error   LONG,
        duration_sec DOUBLE
    ) USING DELTA
""")

# ============================================================
# 2. CARREGAR CONTEXTO DO AGENT_PRE
# ============================================================
def load_state() -> dict:
    if spark.catalog.tableExists(STATE_TABLE):
        row = spark.table(STATE_TABLE).orderBy(
            spark.table(STATE_TABLE)["run_at"].desc()
        ).first()
        if row:
            return row.asDict()
    return {"consecutive_failures": 0}

state = load_state()

try:
    should_process = dbutils.jobs.taskValues.get(
        taskKey="agent_pre", key="should_process", default=False
    )
    bronze_hash = dbutils.jobs.taskValues.get(
        taskKey="agent_pre", key="bronze_hash", default=""
    )
    run_id = dbutils.jobs.taskValues.get(
        taskKey="agent_pre", key="run_id", default="unknown"
    )
    delta_versions = json.loads(
        dbutils.jobs.taskValues.get(
            taskKey="agent_pre", key="delta_versions", default="{}"
        )
    )
except Exception:
    should_process = False
    bronze_hash = ""
    run_id = "standalone"
    delta_versions = {}

# Se nao havia dados novos, apenas registrar skip
if not should_process:
    save_row = Row(
        run_at=datetime.now().isoformat(),
        last_bronze_hash=state.get("last_bronze_hash", ""),
        status="SKIP",
        consecutive_failures=0,
        delta_versions="{}",
    )
    spark.createDataFrame([save_row]).write.format("delta").mode("append").saveAsTable(STATE_TABLE)
    dbutils.notebook.exit("SKIP: no new data to process")

# ============================================================
# 3. COLETAR RESULTADOS DE TODAS AS TASKS
# ============================================================
TASK_KEYS = [
    "bronze_ingestion",
    "silver_dedup",
    "silver_entities",
    "silver_enrichment",
    "gold_analytics",
    "quality_validation",
]

def collect_task_results() -> dict:
    results = {}
    for task in TASK_KEYS:
        try:
            results[task] = dbutils.jobs.taskValues.get(
                taskKey=task, key="status", default="UNKNOWN"
            )
        except Exception:
            results[task] = "UNKNOWN"
    return results

task_results = collect_task_results()
failed_tasks = [t for t, s in task_results.items() if s not in ("SUCCESS", "SKIP")]
all_ok = len(failed_tasks) == 0

logger.info(f"Task results: {task_results}")
logger.info(f"Failed: {failed_tasks}")

# ============================================================
# 4. FUNCOES DE PERSISTENCIA E NOTIFICACAO
# ============================================================
def save_state(bronze_hash: str, status: str, failures: int):
    row = Row(
        run_at=datetime.now().isoformat(),
        last_bronze_hash=bronze_hash,
        status=status,
        consecutive_failures=failures,
        delta_versions=json.dumps(delta_versions),
    )
    spark.createDataFrame([row]).write.format("delta").mode("append").saveAsTable(STATE_TABLE)

def send_notification(level: str, subject: str, body: str):
    """Persiste notificacao em Delta Table e loga."""
    row = Row(
        timestamp=datetime.now().isoformat(),
        level=level,
        subject=subject,
        body=body,
        run_id=run_id,
    )
    spark.createDataFrame([row]).write.format("delta").mode("append").saveAsTable(
        NOTIFICATIONS_TABLE
    )
    logger.info(f"[{level}] {subject}")
    # TODO: integrar webhook (SendGrid/SES) quando AWS estiver configurada

def build_success_body() -> str:
    lines = [f"Run ID: {run_id}", f"Timestamp: {datetime.now().isoformat()}", ""]
    lines.append("Resultados por task:")
    for task, status in task_results.items():
        lines.append(f"  - {task}: {status}")
    return "\n".join(lines)

def build_recovery_body(actions: list) -> str:
    lines = [f"Run ID: {run_id}", f"Tasks com falha: {failed_tasks}", ""]
    lines.append("Acoes de recovery:")
    for action in actions:
        lines.append(f"  - {action}")
    return "\n".join(lines)

def build_failure_body(error: str, failures: int) -> str:
    lines = [
        f"Run ID: {run_id}",
        f"Falhas consecutivas: {failures}",
        f"Tasks com falha: {failed_tasks}",
        f"Erro no recovery: {error}",
        "",
        "Task results:",
    ]
    for task, status in task_results.items():
        lines.append(f"  - {task}: {status}")
    if failures >= MAX_CONSECUTIVE_FAILURES:
        lines.append("")
        lines.append(f"ATENCAO: {failures} falhas consecutivas. Agente PAROU de tentar.")
        lines.append("Intervencao manual necessaria.")
    return "\n".join(lines)

# ============================================================
# 5. FUNCAO DE RECOVERY
# ============================================================
TASK_TO_TABLE = {
    "bronze_ingestion": f"{CATALOG}.bronze.conversations",
    "silver_dedup": f"{CATALOG}.silver.messages_clean",
    "silver_entities": f"{CATALOG}.silver.leads_profile",
    "silver_enrichment": f"{CATALOG}.silver.conversations_enriched",
}

def attempt_recovery(failed: list) -> list:
    """Tenta corrigir tasks com falha via rollback Delta."""
    actions = []

    for task in failed:
        table = TASK_TO_TABLE.get(task)
        if table and table in delta_versions:
            version = delta_versions[table]
            spark.sql(f"RESTORE TABLE {table} TO VERSION AS OF {version}")
            actions.append(f"Rollback {table} para versao {version}")

        elif task == "gold_analytics":
            # Se Silver esta OK, re-executar Gold
            silver_ok = all(
                task_results.get(t) == "SUCCESS"
                for t in ["silver_dedup", "silver_entities", "silver_enrichment"]
            )
            if silver_ok:
                result = dbutils.notebook.run("/notebooks/gold/analytics", 600)
                actions.append(f"Re-executou gold/analytics: {result}")
            else:
                raise Exception("Silver com falha, nao pode recalcular Gold")

        elif task == "quality_validation":
            # Rollback todas as Gold
            for tbl, ver in delta_versions.items():
                if ".gold." in tbl:
                    spark.sql(f"RESTORE TABLE {tbl} TO VERSION AS OF {ver}")
                    actions.append(f"Rollback {tbl} para versao {ver}")

    return actions

# ============================================================
# 6. LOGICA DE DECISAO
# ============================================================
if all_ok:
    # === CENARIO 1: SUCESSO ===
    save_state(bronze_hash, "SUCCESS", 0)
    send_notification(
        level="INFO",
        subject="[Pipeline Medallion] Execucao concluida com sucesso",
        body=build_success_body(),
    )
    dbutils.notebook.exit(f"SUCCESS: run_id={run_id}")

# === CENARIO 2+3: FALHA ===
failures = state.get("consecutive_failures", 0) + 1

# Guardrail: 3+ falhas -> para de tentar
if failures >= MAX_CONSECUTIVE_FAILURES:
    save_state(bronze_hash, "FAILED", failures)
    send_notification(
        level="CRITICAL",
        subject=f"[Pipeline Medallion] CRITICO - {failures} falhas consecutivas",
        body=build_failure_body("Guardrail atingido", failures),
    )
    dbutils.notebook.exit(f"CRITICAL: {failures} consecutive failures, halted")

# Tentar recovery
try:
    recovery_actions = attempt_recovery(failed_tasks)

    # Recovery funcionou
    save_state(bronze_hash, "RECOVERED", 0)
    send_notification(
        level="WARNING",
        subject="[Pipeline Medallion] Correcao automatica realizada",
        body=build_recovery_body(recovery_actions),
    )
    dbutils.notebook.exit(f"RECOVERED: run_id={run_id}, actions={recovery_actions}")

except Exception as recovery_error:
    # Recovery falhou
    save_state(bronze_hash, "FAILED", failures)
    send_notification(
        level="CRITICAL",
        subject="[Pipeline Medallion] FALHA - Correcao automatica nao funcionou",
        body=build_failure_body(str(recovery_error), failures),
    )
    dbutils.notebook.exit(f"FAILED: recovery error - {recovery_error}")
