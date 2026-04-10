# Databricks notebook source
# MAGIC %md
# MAGIC # Workflow Observer - Agente AI Autonomo
# MAGIC Recebe o run_id de um workflow que falhou, coleta contexto completo
# MAGIC (codigo fonte via Workspace API + logs + schema), chama o provider LLM
# MAGIC configurado, cria PR no GitHub e persiste o diagnostico na tabela
# MAGIC `{catalog}.observer.diagnostics` para observabilidade.
# MAGIC
# MAGIC **Tipo:** Observer (independente) | **Trigger:** Sob demanda (via SDK)
# MAGIC **Generico** - funciona com qualquer workflow do workspace.
# MAGIC
# MAGIC _Ultima atualizacao: 2026-04-10_

# COMMAND ----------

# DBTITLE 1,Imports e Setup
from datetime import datetime

import logging
import os
import sys
import time

from databricks.sdk import WorkspaceClient

# Auto-detect o caminho do repositorio Git no Databricks Workspace.
# O notebook vive em observer-framework/notebooks/ — subimos ate a raiz do repo
# Git e adicionamos `observer-framework/` ao sys.path para importar `observer`.
_nb_path = dbutils.notebook.entry_point.getDbutils().notebook().getContext().notebookPath().get()
_repo_root = "/".join(_nb_path.split("/")[:4])
FRAMEWORK_ROOT = f"/Workspace{_repo_root}/observer-framework"
sys.path.insert(0, FRAMEWORK_ROOT)

from observer import (
    ObserverDiagnosticsStore,
    WorkflowObserver,
    check_duplicate,
    load_observer_config,
    parse_failed_tasks_param,
    validate_fix,
)

logger = logging.getLogger("observer")

# COMMAND ----------

# DBTITLE 1,Parametros e Configuracao
# Widgets que identificam a origem (passados pelo sentinel ou SDK)
dbutils.widgets.text("catalog", "medallion", "Catalog Name")
dbutils.widgets.text("scope", "medallion-pipeline", "Secret Scope")
dbutils.widgets.text("source_run_id", "", "Run ID que falhou")
dbutils.widgets.text("source_job_id", "", "Job ID que falhou")
dbutils.widgets.text("source_job_name", "", "Job Name que falhou")
dbutils.widgets.text("failed_tasks", "[]", "Tasks com falha em JSON")

# Widgets que sobrescrevem o observer_config.yaml (deixar vazio = usa YAML/default)
dbutils.widgets.text("llm_provider", "", "LLM Provider (override)")
dbutils.widgets.text("git_provider", "", "Git Provider (override)")
dbutils.widgets.text("dedup_window_hours", "", "Dedup Window hours (override)")
dbutils.widgets.dropdown("dry_run", "false", ["false", "true"], "Dry Run Mode (override)")
dbutils.widgets.text("config_path", "", "Observer config YAML absolute path (override)")

CATALOG = dbutils.widgets.get("catalog")
SCOPE = dbutils.widgets.get("scope")
SOURCE_RUN_ID = dbutils.widgets.get("source_run_id")
SOURCE_JOB_ID = dbutils.widgets.get("source_job_id")
SOURCE_JOB_NAME = dbutils.widgets.get("source_job_name")
FAILED_TASKS = parse_failed_tasks_param(dbutils.widgets.get("failed_tasks"))

# Hierarquia do config: widget `config_path` (do pipeline chamador)
# > template default do framework.
_custom_config_path = dbutils.widgets.get("config_path").strip()
CONFIG_PATH = _custom_config_path or f"{FRAMEWORK_ROOT}/templates/observer_config.yaml"
config = load_observer_config(
    config_path=CONFIG_PATH,
    overrides={
        "llm_provider": dbutils.widgets.get("llm_provider"),
        "git_provider": dbutils.widgets.get("git_provider"),
        "dedup_window_hours": dbutils.widgets.get("dedup_window_hours"),
        "dry_run": dbutils.widgets.get("dry_run"),
    },
)

os.environ["ANTHROPIC_API_KEY"] = dbutils.secrets.get(SCOPE, "anthropic-api-key")
os.environ["GITHUB_TOKEN"] = dbutils.secrets.get(SCOPE, "github-token")
os.environ["GITHUB_REPO"] = dbutils.secrets.get(SCOPE, "github-repo")

# COMMAND ----------

# MAGIC %pip install anthropic PyGithub --quiet

# COMMAND ----------

# DBTITLE 1,Inicializar Observer e Store de Diagnosticos
w = WorkspaceClient()
observer = WorkflowObserver(w)
log = []

log.append(f"Observer iniciado: {datetime.now().isoformat()}")
log.append(
    f"Config: llm={config.llm_provider}/{config.llm_model}, "
    f"git={config.git_provider}/{config.base_branch}, "
    f"dedup={config.dedup_window_hours}h, "
    f"dry_run={config.dry_run}, "
    f"confidence_threshold={config.confidence_threshold:.2f}"
)
if config.dry_run:
    log.append("MODO: DRY-RUN (nao cria PRs, apenas loga e persiste diagnostico)")

# Garante que o schema + tabela de diagnosticos existem (idempotente)
store = ObserverDiagnosticsStore(spark, catalog=CATALOG)
try:
    store.ensure_schema()
    log.append(f"Store pronto: {store.full_table_name}")
except Exception as e:
    log.append(f"WARN: nao foi possivel preparar store de diagnosticos: {e}")

# COMMAND ----------

# DBTITLE 1,Identificar Falhas
if SOURCE_RUN_ID:
    log.append(f"Modo: triggered (run_id={SOURCE_RUN_ID})")
    if SOURCE_JOB_NAME:
        log.append(f"Job origem: {SOURCE_JOB_NAME}")
    if FAILED_TASKS:
        log.append(f"Falhas informadas pelo sentinel: {FAILED_TASKS}")

    failure = observer.build_failure_from_run(
        run_id=int(SOURCE_RUN_ID),
        job_id=int(SOURCE_JOB_ID) if SOURCE_JOB_ID else 0,
        job_name=SOURCE_JOB_NAME or "unknown",
        failed_tasks_hint=FAILED_TASKS or None,
    )
    failures = [failure]
    log.append(f"Tasks com falha: {failure['failed_tasks']}")
else:
    log.append("Modo: busca automatica (ultimas 2h)")
    failures = observer.find_recent_failures(hours=2)
    log.append(f"Falhas encontradas: {len(failures)}")

if not failures or not failures[0].get("failed_tasks"):
    log_str = " | ".join(log)
    dbutils.notebook.exit(f"OK: nenhuma falha para diagnosticar || LOG: {log_str}")

# COMMAND ----------

# DBTITLE 1,Inicializar Providers via Factory
from observer.providers import (
    DiagnosisRequest,
    create_git_provider,
    create_llm_provider,
)

llm = create_llm_provider(
    config.llm_provider,
    api_key=os.environ.get("ANTHROPIC_API_KEY", ""),
    model=config.llm_model,
    max_tokens=config.llm_max_tokens,
)
git = create_git_provider(
    config.git_provider,
    token=os.environ.get("GITHUB_TOKEN", ""),
    repo=os.environ.get("GITHUB_REPO", ""),
    base_branch=config.base_branch,
)

log.append(f"LLM provider: {llm.name}")
log.append(f"Git provider: {git.name}")

# COMMAND ----------

# DBTITLE 1,Persistir Diagnostico na Tabela Delta
def persist_diagnostic(
    failure: dict,
    ctx: dict,
    status: str,
    duration_seconds: float,
    diagnosis=None,
    pr_result=None,
) -> None:
    """Monta DiagnosticRecord e grava na tabela observer.diagnostics.

    Falhas do store sao logadas mas nao interrompem o fluxo principal do
    Observer — persistencia e um diferencial, nao um bloqueio.
    """
    try:
        record = store.build_record(
            job_id=failure.get("job_id", 0),
            job_name=failure.get("job_name", "unknown"),
            run_id=failure.get("run_id", 0),
            failed_task=ctx.get("failed_task", ""),
            error_message=ctx.get("error_message", ""),
            status=status,
            duration_seconds=duration_seconds,
            diagnosis=diagnosis,
            pr_result=pr_result,
        )
        store.save(record)
        log.append(
            f"Diagnostico persistido: status={status}, "
            f"cost=${record.estimated_cost_usd:.4f}"
        )
    except Exception as exc:
        log.append(f"WARN: persistencia falhou: {exc}")

# COMMAND ----------

# DBTITLE 1,Coletar Contexto e Diagnosticar
results = []

for failure in failures:
    log.append(f"--- Processando: {failure['job_name']} ---")

    ctx = observer.build_context(failure, catalog=CATALOG)
    log.append(f"Codigo: {len(ctx['notebook_code'])} chars")
    log.append(f"Erro: {ctx['error_message'][:150]}")

    # Marca o inicio do diagnostico para medir duration_seconds
    diag_start = time.time()

    # Dedup: pula diagnostico se o mesmo erro ja foi resolvido recentemente
    dedup_result = check_duplicate(
        store,
        ctx["error_message"],
        window_hours=config.dedup_window_hours,
        git_provider=git,
    )
    if dedup_result.is_duplicate:
        log.append(f"Cache HIT ({dedup_result.reason})")
        if dedup_result.existing_record:
            prev_pr = dedup_result.existing_record.get("pr_url") or "(sem url)"
            log.append(f"  Diagnostico anterior: {prev_pr}")
        # Registra o skip na tabela para observabilidade
        persist_diagnostic(
            failure,
            ctx,
            status="duplicate_skip",
            duration_seconds=time.time() - diag_start,
            diagnosis=None,
            pr_result=None,
        )
        continue
    log.append(f"Cache MISS ({dedup_result.reason})")

    log.append(f"Chamando {llm.name}...")
    try:
        request = DiagnosisRequest(
            error_message=ctx["error_message"],
            stack_trace=ctx["error_message"],
            failed_task=ctx["failed_task"],
            notebook_code=ctx["notebook_code"],
            schema_info=ctx["schema_info"],
            pipeline_state=ctx["pipeline_state"],
        )
        diagnosis = llm.diagnose(request)

        log.append(f"Provider: {diagnosis.provider}/{diagnosis.model}")
        log.append(f"Tokens: in={diagnosis.input_tokens}, out={diagnosis.output_tokens}")
        log.append(f"Diagnostico: {diagnosis.diagnosis[:200]}")
        log.append(f"Confianca: {diagnosis.confidence:.0%}")

        # Fluxo de decisao do fix: no_fix -> low_confidence -> validation
        # -> dry_run -> criacao de PR. final_status eh setado num unico
        # ponto e persistido no final do bloco. Suporta fixes singular
        # (fixed_code/file_to_fix) ou multi-file (lista fixes).
        pr_result = None
        final_status = "unknown"
        proposed_files = diagnosis.normalized_fixes()
        files_summary = ", ".join(f["file_path"] for f in proposed_files) or "(nenhum)"

        if not proposed_files:
            log.append("LLM nao gerou fix")
            final_status = "no_fix_proposed"
        elif diagnosis.confidence < config.confidence_threshold:
            log.append(
                f"LOW CONFIDENCE ({diagnosis.confidence:.2f} < "
                f"{config.confidence_threshold:.2f}): nao cria PR"
            )
            final_status = "low_confidence"
        else:
            # Validacao pre-PR para cada arquivo proposto
            log.append(f"Validando {len(proposed_files)} arquivo(s): {files_summary}")
            all_valid = True
            validation_errors: list[str] = []
            checks_union: set[str] = set()
            for fix_entry in proposed_files:
                v = validate_fix(fix_entry["code"], fix_entry["file_path"])
                checks_union.update(v.checks_run)
                if not v.valid:
                    all_valid = False
                    for err in v.errors[:3]:
                        validation_errors.append(f"{fix_entry['file_path']}: {err}")
            log.append(
                f"Validacao: checks={sorted(checks_union)}, valid={all_valid}"
            )

            if not all_valid:
                log.append(f"VALIDATION FAILED: {len(validation_errors)} erros")
                for err in validation_errors[:5]:
                    log.append(f"  - {err}")
                final_status = "validation_failed"
            elif config.dry_run:
                log.append(f"DRY-RUN: nao cria PR para {files_summary}")
                for fix_entry in proposed_files:
                    preview = (fix_entry["code"] or "")[:200]
                    log.append(f"  {fix_entry['file_path']}: {preview}...")
                if diagnosis.root_cause:
                    log.append(f"  Root cause: {diagnosis.root_cause[:200]}")
                final_status = "dry_run"
            else:
                log.append(
                    f"Criando PR com {len(proposed_files)} arquivo(s): {files_summary}"
                )
                try:
                    pr_result = git.create_fix_pr(diagnosis, ctx["failed_task"])
                    log.append(f"PR #{pr_result.pr_number}: {pr_result.pr_url}")
                    results.append(
                        {
                            "job": failure["job_name"],
                            "task": ctx["failed_task"],
                            "pr": pr_result.pr_url,
                            "files": len(proposed_files),
                            "confidence": diagnosis.confidence,
                        }
                    )
                    final_status = "success"
                except Exception as e:
                    log.append(f"ERRO PR: {e}")
                    final_status = "pr_failed"

        persist_diagnostic(
            failure,
            ctx,
            status=final_status,
            duration_seconds=time.time() - diag_start,
            diagnosis=diagnosis,
            pr_result=pr_result,
        )

    except Exception as e:
        log.append(f"ERRO AI: {e}")
        persist_diagnostic(
            failure,
            ctx,
            status="llm_failed",
            duration_seconds=time.time() - diag_start,
            diagnosis=None,
            pr_result=None,
        )

# COMMAND ----------

# DBTITLE 1,Resultado
summary = (
    f"Processado: {len(failures)} falhas, "
    f"{len(results)} PRs criados"
)
log.append(summary)

log_str = " | ".join(log)
dbutils.notebook.exit(f"{summary} || LOG: {log_str}")
