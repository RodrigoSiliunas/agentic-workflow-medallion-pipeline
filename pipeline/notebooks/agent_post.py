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
# Identifica quais tasks falharam (qualquer status diferente de SUCCESS/SKIP)
failed_tasks = [t for t, s in task_results.items() if s not in ("SUCCESS", "SKIP")]
all_ok = len(failed_tasks) == 0

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
def ai_diagnose_and_fix(failed: list) -> dict:
    """Usa Claude API para diagnosticar o erro e criar PR com correcao.
    Envia o codigo do notebook, mensagem de erro e schema das tabelas
    para o LLM, que retorna um diagnostico e (opcionalmente) codigo corrigido."""
    from pipeline_lib.agent.llm_diagnostics import diagnose_error
    from pipeline_lib.agent.github_pr import create_fix_pr

    results = {"diagnosis": None, "pr": None, "actions": []}

    for task in failed:
        # Recupera mensagem de erro da task via task values
        try:
            error_msg = dbutils.jobs.taskValues.get(
                taskKey=task, key="error", default="Unknown error"
            )
        except Exception:
            error_msg = f"Task {task} falhou (sem detalhes de erro)"

        # Mapeamento de task para arquivo do notebook correspondente
        task_to_notebook = {
            "bronze_ingestion": "notebooks/bronze/ingest.py",
            "silver_dedup": "notebooks/silver/dedup_clean.py",
            "silver_entities": "notebooks/silver/entities_mask.py",
            "silver_enrichment": "notebooks/silver/enrichment.py",
            "gold_analytics": "notebooks/gold/analytics.py",
            "quality_validation": "notebooks/validation/checks.py",
        }
        notebook_path = task_to_notebook.get(task, "unknown")

        # Le o codigo fonte do notebook para enviar ao LLM
        try:
            notebook_code = open(f"{PIPELINE_ROOT}/{notebook_path}").read()
        except Exception:
            notebook_code = f"[Nao foi possivel ler {notebook_path}]"

        # Coleta schema das tabelas para contexto do LLM
        try:
            schema_info = str(spark.sql(f"SHOW TABLES IN {CATALOG}.bronze").collect())
            schema_info += "\n" + str(spark.sql(f"SHOW TABLES IN {CATALOG}.silver").collect())
            schema_info += "\n" + str(spark.sql(f"SHOW TABLES IN {CATALOG}.gold").collect())
        except Exception:
            schema_info = "[Schema info indisponivel]"

        # Chama Claude API para diagnosticar a falha
        logger.info(f"Chamando Claude API para diagnosticar {task}...")
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
                "consecutive_failures": state.get("consecutive_failures", 0),
            },
        )
        results["diagnosis"] = diagnosis
        results["actions"].append(f"Diagnostico LLM para {task}: {diagnosis.get('diagnosis', 'N/A')}")
        logger.info(f"Diagnostico: {diagnosis.get('diagnosis', 'N/A')}")
        logger.info(f"Confianca: {diagnosis.get('confidence', 0)}")

        # Se o LLM gerou codigo corrigido, cria PR no GitHub
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

        # Apenas diagnostica a primeira task falhada (a mais provavel causa raiz)
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
# Fluxo de decisao:
# 1. Tudo OK -> salva SUCCESS, notifica, sai
# 2. Falhas >= limite -> aciona IA, salva FAILED/CRITICAL
# 3. Falhas < limite -> tenta rollback, se falhar aciona IA
if all_ok:
    save_state(bronze_hash, "SUCCESS", 0)
    send_notification(
        level="INFO",
        subject="[Pipeline Medallion] Execucao concluida com sucesso",
        body=build_success_body(),
    )
    dbutils.notebook.exit(f"SUCCESS: run_id={run_id}")

# Incrementa contador de falhas consecutivas
failures = state.get("consecutive_failures", 0) + 1

# Se atingiu o limite de falhas, aciona o agente de IA diretamente
if failures >= MAX_CONSECUTIVE_FAILURES:
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

# Tenta recovery via rollback Delta primeiro
try:
    recovery_actions = attempt_recovery(failed_tasks)

    save_state(bronze_hash, "RECOVERED", 0)
    send_notification(
        level="WARNING",
        subject="[Pipeline Medallion] Correcao automatica realizada (rollback)",
        body=build_recovery_body(recovery_actions),
    )
    dbutils.notebook.exit(f"RECOVERED: run_id={run_id}, actions={recovery_actions}")

except Exception as recovery_error:
    # Rollback falhou -- aciona agente de IA como fallback
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
        # Todos os metodos de recovery falharam -- salva como FAILED
        save_state(bronze_hash, "FAILED", failures)
        send_notification(
            level="CRITICAL",
            subject="[Pipeline Medallion] FALHA TOTAL - Rollback e AI falharam",
            body=build_failure_body(f"Rollback: {recovery_error} | AI: {ai_error}", failures),
        )
        dbutils.notebook.exit(f"FAILED: all recovery methods exhausted")
