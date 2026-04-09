# Databricks notebook source
# MAGIC %md
# MAGIC # Agent Post-Check (Task 5)
# MAGIC Verifica resultados, recovery com rollback Delta, notificacoes por email.
# MAGIC **run_if: ALL_DONE** — roda SEMPRE, mesmo se tasks anteriores falharam.

# COMMAND ----------

import json
import logging
import sys
import time
from datetime import datetime

from pyspark.sql import Row

logger = logging.getLogger("agent_post")

# COMMAND ----------

# ============================================================
# IMPORTAR S3Lake (boto3 + Databricks Secrets)
# ============================================================
sys.path.insert(0, "/Workspace/Repos/rodrigosiliunas1@gmail.com/agentic-workflow-medallion-pipeline/pipeline")
from pipeline_lib.storage import S3Lake

lake = S3Lake(dbutils)

# COMMAND ----------

# ============================================================
# CONFIGURACAO
# ============================================================
CATALOG = spark.conf.get("pipeline.catalog", "medallion")
STATE_TABLE = f"{CATALOG}.pipeline.state"
NOTIFICATIONS_TABLE = f"{CATALOG}.pipeline.notifications"
METRICS_TABLE = f"{CATALOG}.pipeline.metrics"
MAX_CONSECUTIVE_FAILURES = 3

# COMMAND ----------

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

# COMMAND ----------

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
    # Upload state para S3
    _tmp = lake.make_temp_dir("pipeline_state_skip_")
    _local = f"{_tmp}/state"
    spark.table(STATE_TABLE).write.format("delta").mode("overwrite").save(_local)
    lake.upload_dir(_local, "pipeline/state/")
    dbutils.notebook.exit("SKIP: no new data to process")

# COMMAND ----------

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

# COMMAND ----------

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
    state_df = spark.createDataFrame([row])
    state_df.write.format("delta").mode("append").saveAsTable(STATE_TABLE)

    # Upload state para S3
    tmp = lake.make_temp_dir("pipeline_state_")
    local_path = f"{tmp}/state"
    spark.table(STATE_TABLE).write.format("delta").mode("overwrite").save(local_path)
    lake.upload_dir(local_path, "pipeline/state/")

def send_notification(level: str, subject: str, body: str):
    """Persiste notificacao em Delta Table e loga."""
    row = Row(
        timestamp=datetime.now().isoformat(),
        level=level,
        subject=subject,
        body=body,
        run_id=run_id,
    )
    notif_df = spark.createDataFrame([row])
    notif_df.write.format("delta").mode("append").saveAsTable(
        NOTIFICATIONS_TABLE
    )
    logger.info(f"[{level}] {subject}")

    # Upload notifications para S3
    tmp = lake.make_temp_dir("pipeline_notif_")
    local_path = f"{tmp}/notifications"
    spark.table(NOTIFICATIONS_TABLE).write.format("delta").mode("overwrite").save(local_path)
    lake.upload_dir(local_path, "pipeline/notifications/")

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

# COMMAND ----------

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

# COMMAND ----------

# ============================================================
# 6. FUNCOES DO AGENTE DE IA (LLM + GitHub PR)
# ============================================================
# (sys.path ja configurado no topo do notebook para S3Lake)

def ai_diagnose_and_fix(failed: list) -> dict:
    """Usa Claude API para diagnosticar o erro e criar PR com correcao."""
    from pipeline_lib.agent.llm_diagnostics import diagnose_error
    from pipeline_lib.agent.github_pr import create_fix_pr

    results = {"diagnosis": None, "pr": None, "actions": []}

    for task in failed:
        # Coletar contexto do erro
        try:
            error_msg = dbutils.jobs.taskValues.get(
                taskKey=task, key="error", default="Unknown error"
            )
        except Exception:
            error_msg = f"Task {task} falhou (sem detalhes de erro)"

        # Ler codigo do notebook que falhou
        task_to_notebook = {
            "bronze_ingestion": "notebooks/bronze/ingest.py",
            "silver_dedup": "notebooks/silver/dedup_clean.py",
            "silver_entities": "notebooks/silver/entities_mask.py",
            "silver_enrichment": "notebooks/silver/enrichment.py",
            "gold_analytics": "notebooks/gold/analytics.py",
            "quality_validation": "notebooks/validation/checks.py",
        }
        notebook_path = task_to_notebook.get(task, "unknown")

        try:
            notebook_code = open(f"/Workspace/Repos/{notebook_path}").read()
        except Exception:
            notebook_code = f"[Nao foi possivel ler {notebook_path}]"

        # Coletar schema info
        try:
            schema_info = str(spark.sql(f"SHOW TABLES IN {CATALOG}.bronze").collect())
            schema_info += "\n" + str(spark.sql(f"SHOW TABLES IN {CATALOG}.silver").collect())
            schema_info += "\n" + str(spark.sql(f"SHOW TABLES IN {CATALOG}.gold").collect())
        except Exception:
            schema_info = "[Schema info indisponivel]"

        # Chamar Claude API para diagnostico
        logger.info(f"Chamando Claude API para diagnosticar {task}...")
        diagnosis = diagnose_error(
            error_message=error_msg,
            stack_trace=error_msg,  # Em producao, capturar stack trace completo
            failed_task=task,
            notebook_code=notebook_code,
            schema_info=schema_info,
            pipeline_state={
                "run_id": run_id,
                "task_results": task_results,
                "delta_versions": delta_versions,
                "consecutive_failures": state.get("consecutive_failures", 0),
            },
        )
        results["diagnosis"] = diagnosis
        results["actions"].append(f"Diagnostico LLM para {task}: {diagnosis.get('diagnosis', 'N/A')}")
        logger.info(f"Diagnostico: {diagnosis.get('diagnosis', 'N/A')}")
        logger.info(f"Confianca: {diagnosis.get('confidence', 0)}")

        # Se tem codigo corrigido e confianca razoavel, criar PR
        if diagnosis.get("fixed_code") and diagnosis.get("file_to_fix"):
            logger.info(f"Criando PR com correcao para {diagnosis['file_to_fix']}...")
            try:
                pr_result = create_fix_pr(
                    fix_description=diagnosis.get("fix_description", ""),
                    diagnosis=diagnosis.get("diagnosis", ""),
                    file_path=diagnosis["file_to_fix"],
                    fixed_code=diagnosis["fixed_code"],
                    failed_task=task,
                    confidence=diagnosis.get("confidence", 0.5),
                )
                results["pr"] = pr_result
                results["actions"].append(
                    f"PR criado: {pr_result['pr_url']} (branch: {pr_result['branch_name']})"
                )
                logger.info(f"PR criado: {pr_result['pr_url']}")
            except Exception as pr_error:
                logger.error(f"Erro ao criar PR: {pr_error}")
                results["actions"].append(f"Falha ao criar PR: {pr_error}")

        # Processar apenas a primeira task com falha (uma de cada vez)
        break

    return results

def build_ai_notification_body(diagnosis: dict, pr: dict | None) -> str:
    """Constroi corpo do email com diagnostico do LLM + link do PR."""
    lines = [
        f"Run ID: {run_id}",
        f"Timestamp: {datetime.now().isoformat()}",
        "",
        "=" * 50,
        "DIAGNOSTICO DO AGENTE DE IA",
        "=" * 50,
        "",
        f"Problema: {diagnosis.get('diagnosis', 'N/A')}",
        f"Causa raiz: {diagnosis.get('root_cause', 'N/A')}",
        f"Confianca: {diagnosis.get('confidence', 0):.0%}",
        "",
        f"Correcao proposta: {diagnosis.get('fix_description', 'N/A')}",
        "",
    ]

    if pr:
        lines.extend([
            "=" * 50,
            "PULL REQUEST CRIADO",
            "=" * 50,
            "",
            f"URL: {pr['pr_url']}",
            f"Branch: {pr['branch_name']}",
            "",
            "Por favor, revise e aprove o PR para aplicar a correcao.",
        ])
    else:
        lines.extend([
            "Nao foi possivel criar PR automaticamente.",
            "Intervencao manual necessaria.",
        ])

    if diagnosis.get("additional_notes"):
        lines.extend(["", f"Notas adicionais: {diagnosis['additional_notes']}"])

    lines.extend([
        "",
        "---",
        "Task results:",
    ])
    for task, status in task_results.items():
        lines.append(f"  - {task}: {status}")

    return "\n".join(lines)

# COMMAND ----------

# ============================================================
# 7. LOGICA DE DECISAO
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

# Guardrail: 3+ falhas -> para de tentar, mas ainda diagnostica
if failures >= MAX_CONSECUTIVE_FAILURES:
    # Mesmo no guardrail, tenta diagnosticar com LLM
    try:
        ai_result = ai_diagnose_and_fix(failed_tasks)
        diagnosis = ai_result.get("diagnosis", {})
        pr = ai_result.get("pr")
        body = build_ai_notification_body(diagnosis, pr)
        body += f"\n\nATENCAO: {failures} falhas consecutivas. Agente PAROU de tentar."
    except Exception as ai_error:
        body = build_failure_body(f"Guardrail + AI error: {ai_error}", failures)

    save_state(bronze_hash, "FAILED", failures)
    send_notification(
        level="CRITICAL",
        subject=f"[Pipeline Medallion] CRITICO - {failures} falhas consecutivas + diagnostico AI",
        body=body,
    )
    dbutils.notebook.exit(f"CRITICAL: {failures} failures, PR={'created' if pr else 'none'}")

# Tentar recovery (rollback Delta)
try:
    recovery_actions = attempt_recovery(failed_tasks)

    # Recovery de dados funcionou
    save_state(bronze_hash, "RECOVERED", 0)
    send_notification(
        level="WARNING",
        subject="[Pipeline Medallion] Correcao automatica realizada (rollback)",
        body=build_recovery_body(recovery_actions),
    )
    dbutils.notebook.exit(f"RECOVERED: run_id={run_id}, actions={recovery_actions}")

except Exception as recovery_error:
    # Recovery de dados falhou -> acionar agente de IA
    logger.warning(f"Rollback falhou: {recovery_error}. Acionando agente de IA...")

    try:
        ai_result = ai_diagnose_and_fix(failed_tasks)
        diagnosis = ai_result.get("diagnosis", {})
        pr = ai_result.get("pr")

        save_state(bronze_hash, "AI_DIAGNOSED", failures)
        send_notification(
            level="WARNING",
            subject="[Pipeline Medallion] Agente AI diagnosticou o erro e criou PR",
            body=build_ai_notification_body(diagnosis, pr),
        )
        dbutils.notebook.exit(
            f"AI_DIAGNOSED: run_id={run_id}, "
            f"pr={pr['pr_url'] if pr else 'none'}, "
            f"confidence={diagnosis.get('confidence', 0)}"
        )

    except Exception as ai_error:
        # Nem rollback nem AI funcionaram
        save_state(bronze_hash, "FAILED", failures)
        send_notification(
            level="CRITICAL",
            subject="[Pipeline Medallion] FALHA TOTAL - Rollback e AI falharam",
            body=build_failure_body(f"Rollback: {recovery_error} | AI: {ai_error}", failures),
        )
        dbutils.notebook.exit(f"FAILED: all recovery methods exhausted")
