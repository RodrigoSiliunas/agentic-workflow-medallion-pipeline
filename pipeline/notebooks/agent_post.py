# Databricks notebook source
# MAGIC %md
# MAGIC # Agent Post-Check (Task 5)
# MAGIC Verifica resultados de todas as tasks, executa recovery com rollback Delta
# MAGIC quando necessario, aciona agente de IA (Claude API + GitHub PR) em caso de
# MAGIC falhas persistentes, e persiste notificacoes por email.
# MAGIC
# MAGIC **run_if: ALL_DONE** -- roda SEMPRE, mesmo se tasks anteriores falharam.
# MAGIC
# MAGIC **Camada:** Orquestrador | **Dependencia:** todas as tasks anteriores
# MAGIC
# MAGIC _Ultima atualizacao: 2026-04-09_

# COMMAND ----------

# DBTITLE 1,Imports e Setup
import json
import logging
import os
import sys
import time
from datetime import datetime

from pyspark.sql import Row

# Auto-detect repo path from this notebook's location
_nb_path = dbutils.notebook.entry_point.getDbutils().notebook().getContext().notebookPath().get()
_repo_root = "/".join(_nb_path.split("/")[:4])
PIPELINE_ROOT = f"/Workspace{_repo_root}/pipeline"
sys.path.insert(0, PIPELINE_ROOT)

from pipeline_lib.storage import S3Lake

# COMMAND ----------

# DBTITLE 1,Parametros
dbutils.widgets.text("catalog", "medallion", "Catalog Name")
dbutils.widgets.text("scope", "medallion-pipeline", "Secret Scope")

CATALOG = dbutils.widgets.get("catalog")
SCOPE = dbutils.widgets.get("scope")

# Inicializa o lake client e o logger
lake = S3Lake(dbutils, spark, scope=SCOPE)
logger = logging.getLogger("agent_post")

# Carregar credenciais do agente AI a partir dos Databricks Secrets
# Necessario para o LLM diagnostics (Claude API) e GitHub PR
os.environ["ANTHROPIC_API_KEY"] = dbutils.secrets.get(SCOPE, "anthropic-api-key")
os.environ["GITHUB_TOKEN"] = dbutils.secrets.get(SCOPE, "github-token")
os.environ["GITHUB_REPO"] = dbutils.secrets.get(SCOPE, "github-repo")

# COMMAND ----------

# DBTITLE 1,Constantes e Tabelas de Apoio
# Nomes das tabelas de controle do pipeline
STATE_TABLE = f"{CATALOG}.pipeline.state"
NOTIFICATIONS_TABLE = f"{CATALOG}.pipeline.notifications"
METRICS_TABLE = f"{CATALOG}.pipeline.metrics"

# Limite de falhas consecutivas antes de acionar o agente de IA
MAX_CONSECUTIVE_FAILURES = 3

# COMMAND ----------

# DBTITLE 1,Criar Tabelas de Apoio
# Tabela de notificacoes -- persiste alertas enviados por email
spark.sql(f"""
    CREATE TABLE IF NOT EXISTS {NOTIFICATIONS_TABLE} (
        timestamp    STRING,
        level        STRING,
        subject      STRING,
        body         STRING,
        run_id       STRING
    ) USING DELTA
""")

# Tabela de metricas -- registra performance de cada task
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

# DBTITLE 1,Carregar Contexto do Agent Pre
def load_state() -> dict:
    """Carrega o ultimo estado salvo na tabela pipeline.state."""
    if spark.catalog.tableExists(STATE_TABLE):
        from pyspark.sql import functions as F
        row = spark.table(STATE_TABLE).orderBy(
            F.col("run_at").desc()
        ).first()
        if row:
            return row.asDict()
    return {"consecutive_failures": 0}

state = load_state()

# Tenta recuperar task values setados pelo agent_pre
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
    # Execucao standalone (sem workflow) -- usa valores default
    should_process = False
    bronze_hash = ""
    run_id = "standalone"
    delta_versions = {}

# Se agent_pre decidiu que nao ha dados novos, apenas persiste o estado e sai
if not should_process:
    save_row = Row(
        run_at=datetime.now().isoformat(),
        last_bronze_hash=state.get("last_bronze_hash", ""),
        status="SKIP",
        consecutive_failures=0,
        delta_versions="{}",
    )
    spark.createDataFrame([save_row]).write.format("delta").mode("append").saveAsTable(STATE_TABLE)
    lake.write_parquet(spark.table(STATE_TABLE), "pipeline/state/")
    dbutils.notebook.exit("SKIP: no new data to process")

# COMMAND ----------

# DBTITLE 1,Coletar Resultados das Tasks
# Lista de todas as tasks do workflow que precisam ser verificadas
TASK_KEYS = [
    "bronze_ingestion",
    "silver_dedup",
    "silver_entities",
    "silver_enrichment",
    "gold_analytics",
    "quality_validation",
]

def collect_task_results() -> dict:
    """Coleta o status de cada task via task values do Databricks."""
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
# Status que indicam sucesso ou que a task nao precisa de acao
# UNKNOWN = task nunca rodou (upstream failure) — nao eh uma falha propria
ACCEPTED_STATUS = ("SUCCESS", "SKIP", "PASS", "UNKNOWN")
failed_tasks = [t for t, s in task_results.items() if s not in ACCEPTED_STATUS]
all_ok = len(failed_tasks) == 0

print(f"\n  Task results: {task_results}")
print(f"  Failed (excluindo UNKNOWN): {failed_tasks}")
logger.info(f"Task results: {task_results}")
logger.info(f"Failed: {failed_tasks}")

# COMMAND ----------

# DBTITLE 1,Funcoes de Persistencia e Notificacao
def save_state(bronze_hash: str, status: str, failures: int):
    """Persiste o estado da execucao atual na tabela pipeline.state."""
    row = Row(
        run_at=datetime.now().isoformat(),
        last_bronze_hash=bronze_hash,
        status=status,
        consecutive_failures=failures,
        delta_versions=json.dumps(delta_versions),
    )
    state_df = spark.createDataFrame([row])
    state_df.write.format("delta").mode("append").saveAsTable(STATE_TABLE)
    # Backup em Parquet no S3
    lake.write_parquet(spark.table(STATE_TABLE), "pipeline/state/")

def send_notification(level: str, subject: str, body: str):
    """Persiste notificacao em Delta Table e loga.
    Em producao, poderia enviar email via SES/SNS."""
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
    # Backup em Parquet no S3
    lake.write_parquet(spark.table(NOTIFICATIONS_TABLE), "pipeline/notifications/")

def build_success_body() -> str:
    """Constroi corpo do email de sucesso com resumo de todas as tasks."""
    lines = [f"Run ID: {run_id}", f"Timestamp: {datetime.now().isoformat()}", ""]
    lines.append("Resultados por task:")
    for task, status in task_results.items():
        lines.append(f"  - {task}: {status}")
    return "\n".join(lines)

def build_recovery_body(actions: list) -> str:
    """Constroi corpo do email de recovery com acoes tomadas."""
    lines = [f"Run ID: {run_id}", f"Tasks com falha: {failed_tasks}", ""]
    lines.append("Acoes de recovery:")
    for action in actions:
        lines.append(f"  - {action}")
    return "\n".join(lines)

def build_failure_body(error: str, failures: int) -> str:
    """Constroi corpo do email de falha critica com detalhes do erro."""
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
    # Alerta de intervencao manual quando limite de falhas atingido
    if failures >= MAX_CONSECUTIVE_FAILURES:
        lines.append("")
        lines.append(f"ATENCAO: {failures} falhas consecutivas. Agente PAROU de tentar.")
        lines.append("Intervencao manual necessaria.")
    return "\n".join(lines)

# COMMAND ----------

# DBTITLE 1,Recovery via Rollback Delta
# Mapeamento de task para a tabela principal que ela escreve
TASK_TO_TABLE = {
    "bronze_ingestion": f"{CATALOG}.bronze.conversations",
    "silver_dedup": f"{CATALOG}.silver.messages_clean",
    "silver_entities": f"{CATALOG}.silver.leads_profile",
    "silver_enrichment": f"{CATALOG}.silver.conversations_enriched",
}

def attempt_recovery(failed: list) -> list:
    """Tenta corrigir tasks com falha via rollback Delta.
    Para cada task falhada, restaura a tabela correspondente para
    a versao capturada pelo agent_pre antes da execucao."""
    actions = []

    for task in failed:
        table = TASK_TO_TABLE.get(task)
        if table and table in delta_versions:
            # Rollback para a versao pre-execucao
            version = delta_versions[table]
            spark.sql(f"RESTORE TABLE {table} TO VERSION AS OF {version}")
            actions.append(f"Rollback {table} para versao {version}")

        elif task == "gold_analytics":
            # Se Gold falhou mas Silver esta OK, re-executa Gold
            silver_ok = all(
                task_results.get(t) == "SUCCESS"
                for t in ["silver_dedup", "silver_entities", "silver_enrichment"]
            )
            if silver_ok:
                _notebook_base = f"{_repo_root}/pipeline/notebooks"
                result = dbutils.notebook.run(f"{_notebook_base}/gold/analytics", 600)
                actions.append(f"Re-executou gold/analytics: {result}")
            else:
                raise Exception("Silver com falha, nao pode recalcular Gold")

        elif task == "quality_validation":
            # Validation falhou -- rollback de todas as tabelas Gold
            for tbl, ver in delta_versions.items():
                if ".gold." in tbl:
                    spark.sql(f"RESTORE TABLE {tbl} TO VERSION AS OF {ver}")
                    actions.append(f"Rollback {tbl} para versao {ver}")

    return actions

# COMMAND ----------

# DBTITLE 1,Instalar Dependencias do Agente AI
# anthropic: Claude API para diagnostico inteligente de erros
# PyGithub: criacao automatica de PRs com correcoes

# COMMAND ----------

# MAGIC %pip install anthropic PyGithub --quiet

# COMMAND ----------

# DBTITLE 1,Agente de IA (LLM + GitHub PR)
def ai_diagnose_and_fix(failed: list, log: list) -> dict:
    """Usa Claude Opus para diagnosticar o erro e criar PR."""
    from pipeline_lib.agent.llm_diagnostics import diagnose_error
    from pipeline_lib.agent.github_pr import create_fix_pr

    results = {"diagnosis": None, "pr": None, "actions": []}

    for task in failed:
        log.append(f"[AI] Diagnosticando: {task}")

        # 1. Recuperar erro
        try:
            error_msg = dbutils.jobs.taskValues.get(
                taskKey=task, key="error", default="Unknown error"
            )
        except Exception:
            error_msg = f"Task {task} falhou (sem detalhes)"
        log.append(f"[AI] Erro: {error_msg[:200]}")

        # 2. Ler codigo fonte
        task_to_notebook = {
            "bronze_ingestion": "notebooks/bronze/ingest.py",
            "silver_dedup": "notebooks/silver/dedup_clean.py",
            "silver_entities": "notebooks/silver/entities_mask.py",
            "silver_enrichment": "notebooks/silver/enrichment.py",
            "gold_analytics": "notebooks/gold/analytics.py",
            "quality_validation": "notebooks/validation/checks.py",
        }
        nb_path = task_to_notebook.get(task, "unknown")
        full_path = f"{PIPELINE_ROOT}/{nb_path}"
        try:
            notebook_code = open(full_path).read()
            log.append(f"[AI] Codigo: {nb_path} ({notebook_code.count(chr(10))} linhas)")
        except Exception:
            # Fallback: tentar sem /Workspace prefix
            alt_path = full_path.replace("/Workspace", "")
            try:
                notebook_code = open(alt_path).read()
                log.append(f"[AI] Codigo (alt): {nb_path} ({notebook_code.count(chr(10))} linhas)")
            except Exception as e:
                notebook_code = f"[Nao foi possivel ler {nb_path}] paths tentados: {full_path}, {alt_path}. Erro: {e}"
                log.append(f"[AI] WARN: nao leu {nb_path}")

        # 3. Schema detalhado (DESCRIBE com colunas)
        schema_parts = []
        for schema in ["bronze", "silver", "gold"]:
            try:
                tables = spark.sql(f"SHOW TABLES IN {CATALOG}.{schema}").collect()
                for t in tables:
                    tname = f"{CATALOG}.{schema}.{t.tableName}"
                    cols = spark.sql(f"DESCRIBE TABLE {tname}").collect()
                    col_str = ", ".join(f"{c.col_name}:{c.data_type}" for c in cols[:20])
                    schema_parts.append(f"{tname}: [{col_str}]")
            except Exception:
                schema_parts.append(f"{CATALOG}.{schema}: [indisponivel]")
        schema_info = "\n".join(schema_parts)
        log.append(f"[AI] Schema: {len(schema_parts)} tabelas coletadas")

        # 4. Chamar Claude Opus
        log.append("[AI] Chamando Claude Opus 4.6...")
        diagnosis = diagnose_error(
            error_message=error_msg,
            stack_trace=error_msg,
            failed_task=task,
            notebook_code=notebook_code,
            schema_info=schema_info,
            pipeline_state={
                "run_id": run_id,
                "task_results": task_results,
                "delta_versions": delta_versions,
                "failures": state.get("consecutive_failures", 0),
            },
        )
        results["diagnosis"] = diagnosis

        conf = diagnosis.get("confidence", 0)
        model = diagnosis.get("_model", "unknown")
        in_tok = diagnosis.get("_input_tokens", 0)
        out_tok = diagnosis.get("_output_tokens", 0)
        log.append(f"[AI] Modelo: {model} (in={in_tok}, out={out_tok})")
        log.append(f"[AI] Diagnostico: {diagnosis.get('diagnosis', 'N/A')[:200]}")
        log.append(f"[AI] Causa raiz: {diagnosis.get('root_cause', 'N/A')[:200]}")
        log.append(f"[AI] Confianca: {conf:.0%}")
        log.append(f"[AI] Fix: {diagnosis.get('fix_description', 'N/A')[:200]}")

        # 5. Criar PR
        if diagnosis.get("fixed_code") and diagnosis.get("file_to_fix"):
            log.append(f"[AI] Criando PR para {diagnosis['file_to_fix']}...")
            try:
                pr_result = create_fix_pr(
                    fix_description=diagnosis.get("fix_description", ""),
                    diagnosis=diagnosis.get("diagnosis", ""),
                    file_path=diagnosis["file_to_fix"],
                    fixed_code=diagnosis["fixed_code"],
                    failed_task=task,
                    confidence=conf,
                )
                results["pr"] = pr_result
                log.append(f"[AI] PR #{pr_result['pr_number']}: {pr_result['pr_url']}")
            except Exception as e:
                log.append(f"[AI] ERRO PR: {e}")
        else:
            log.append("[AI] LLM nao gerou codigo — intervencao manual")

        break  # Diagnostica apenas a primeira task falhada

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

    # Notas adicionais do LLM (se houver)
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

# DBTITLE 1,Logica de Decisao Principal
# Log buffer — acumula todos os passos e aparece no notebook.exit()
# IMPORTANTE: dbutils.notebook.exit() NUNCA dentro de try/except
# porque ele lanca excecao especial que seria capturada pelo except
log = []
exit_status = "UNKNOWN"
exit_details = ""

log.append(f"Run: {run_id}")
log.append(f"Failed tasks: {failed_tasks if failed_tasks else 'nenhuma'}")
log.append(f"All OK: {all_ok}")
log.append(f"Falhas anteriores: {state.get('consecutive_failures', 0)}")

if all_ok:
    # Tudo OK — salva SUCCESS
    log.append("DECISAO: Tudo OK")
    save_state(bronze_hash, "SUCCESS", 0)
    send_notification(
        level="INFO",
        subject="[Pipeline] Execucao com sucesso",
        body=build_success_body(),
    )
    exit_status = "SUCCESS"
    exit_details = f"run_id={run_id}"
else:
    # Falha detectada — inicia recovery
    failures = state.get("consecutive_failures", 0) + 1
    log.append(f"FALHA: {len(failed_tasks)} tasks, consecutivas={failures}/{MAX_CONSECUTIVE_FAILURES}")

    # Passo 1: Rollback Delta
    log.append("TENTATIVA 1: Rollback Delta")
    recovery_ok = False
    recovery_actions = []
    try:
        recovery_actions = attempt_recovery(failed_tasks)
        recovery_ok = True
        log.append(f"ROLLBACK OK: {recovery_actions}")
    except Exception as e:
        log.append(f"ROLLBACK FALHOU: {e}")

    # Passo 2: Se rollback falhou OU muitas falhas, aciona AI
    ai_needed = not recovery_ok or failures >= MAX_CONSECUTIVE_FAILURES
    ai_result = None
    if ai_needed:
        log.append("TENTATIVA 2: Agente AI (Claude Opus + GitHub PR)")
        try:
            ai_result = ai_diagnose_and_fix(failed_tasks, log)
        except Exception as e:
            log.append(f"AGENTE AI FALHOU: {e}")

    # Decidir resultado final e persistir
    if recovery_ok and not ai_needed:
        save_state(bronze_hash, "RECOVERED", 0)
        send_notification(
            level="WARNING",
            subject="[Pipeline] Correcao automatica (rollback)",
            body=build_recovery_body(recovery_actions),
        )
        exit_status = "RECOVERED"
        exit_details = f"actions={recovery_actions}"

    elif ai_result and ai_result.get("diagnosis"):
        diagnosis = ai_result.get("diagnosis", {})
        pr = ai_result.get("pr")
        pr_url = pr["pr_url"] if pr else "none"
        conf = diagnosis.get("confidence", 0)

        save_state(bronze_hash, "AI_DIAGNOSED", failures)
        send_notification(
            level="WARNING",
            subject="[Pipeline] Agente AI diagnosticou e criou PR",
            body=build_ai_notification_body(diagnosis, pr),
        )
        exit_status = "AI_DIAGNOSED"
        exit_details = f"pr={pr_url}, confidence={conf:.0%}"

    else:
        save_state(bronze_hash, "FAILED", failures)
        send_notification(
            level="CRITICAL",
            subject="[Pipeline] FALHA TOTAL",
            body=build_failure_body("Recovery e AI falharam", failures),
        )
        exit_status = "FAILED"
        exit_details = "all recovery methods exhausted"

# Unico ponto de saida — FORA de qualquer try/except
log_str = " | ".join(log)
dbutils.notebook.exit(f"{exit_status}: {exit_details} || LOG: {log_str}")
