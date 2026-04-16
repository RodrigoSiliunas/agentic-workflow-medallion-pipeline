"""Workflow Observer — agente genérico que monitora workflows Databricks.

Detecta falhas em qualquer workflow do workspace, coleta contexto
completo (logs, código, schema) para enviar ao LLM provider.

Desacoplado de qualquer pipeline específico.
"""

from __future__ import annotations

import base64
import logging
from datetime import datetime, timedelta

from databricks.sdk import WorkspaceClient

from observer.redaction import redact
from observer.triggering import extract_failed_task_keys

logger = logging.getLogger("workflow_observer")


class WorkflowObserver:
    """Observa workflows Databricks e coleta contexto de falhas."""

    def __init__(self, w: WorkspaceClient):
        self.w = w

    def find_recent_failures(
        self,
        hours: int = 1,
        workflow_name: str | None = None,
    ) -> list[dict]:
        """Encontra runs que falharam nas últimas N horas."""
        failures = []
        start_time = int(
            (datetime.now() - timedelta(hours=hours)).timestamp() * 1000
        )

        jobs = list(self.w.jobs.list(name=workflow_name))

        for job in jobs:
            runs = list(
                self.w.jobs.list_runs(
                    job_id=job.job_id,
                    start_time_from=start_time,
                    limit=5,
                )
            )
            for run in runs:
                result = str(run.state.result_state) if run.state else ""
                if "FAILED" not in result and "WITH_FAILURES" not in result:
                    continue

                failure = self.build_failure_from_run(
                    run_id=run.run_id,
                    job_id=job.job_id,
                    job_name=job.settings.name,
                )
                if failure["failed_tasks"]:
                    failures.append(failure)

        return failures

    def build_failure_from_run(
        self,
        run_id: int,
        job_id: int = 0,
        job_name: str = "unknown",
        failed_tasks_hint: list[str] | None = None,
    ) -> dict:
        """Constrói dict de falha a partir de um run_id.

        Pode ser chamado diretamente (modo triggered) ou via
        find_recent_failures (modo busca).
        """
        run = self.w.jobs.get_run(run_id=run_id)
        failed_tasks = list(failed_tasks_hint or extract_failed_task_keys(run.tasks or []))
        errors = {}

        for task in run.tasks or []:
            if task.task_key not in failed_tasks:
                continue
            try:
                out = self.w.jobs.get_run_output(run_id=task.run_id)
                error = out.error or "Unknown error"
            except Exception:
                error = "Could not retrieve error"
            # PII redact antes de truncar: dados brutos de erro podem
            # conter CPF/email/telefone vindos da execução do pipeline.
            errors[task.task_key] = redact(error)[:500]

        return {
            "job_id": job_id or getattr(run, "job_id", 0),
            "job_name": job_name or run.run_name or "unknown",
            "run_id": run_id,
            "failed_tasks": failed_tasks,
            "errors": errors,
            "timestamp": str(run.start_time),
        }

    def collect_notebook_code(self, run_id: int) -> dict[str, str]:
        """Lê código fonte de cada notebook via Workspace API."""
        codes = {}
        run = self.w.jobs.get_run(run_id=run_id)

        for task in run.tasks or []:
            if not task.notebook_task:
                continue
            nb_path = task.notebook_task.notebook_path
            try:
                export = self.w.workspace.export(
                    path=nb_path, format="SOURCE"
                )
                if export.content:
                    code = base64.b64decode(export.content).decode("utf-8")
                    codes[task.task_key] = code
                    logger.info(f"Código: {task.task_key} ({len(code)} chars)")
            except Exception as e:
                codes[task.task_key] = f"[Erro ao ler {nb_path}: {e}]"
                logger.warning(f"Não leu {nb_path}: {e}")

        return codes

    def collect_schema_info(
        self,
        catalog: str = "medallion",
        schemas: list[str] | None = None,
    ) -> str:
        """Coleta schema detalhado das tabelas do catálogo.

        Args:
            catalog: Nome do catálogo no Unity Catalog
            schemas: Lista de schemas a coletar. Se None, descobre automaticamente.
        """
        # Se não especificado, descobre schemas do catálogo
        if schemas is None:
            try:
                discovered = list(self.w.schemas.list(catalog_name=catalog))
                schemas = [s.name for s in discovered if s.name != "information_schema"]
            except Exception:
                schemas = []

        parts = []
        for schema in schemas:
            try:
                tables = list(
                    self.w.tables.list(catalog_name=catalog, schema_name=schema)
                )
                for t in tables:
                    cols = [
                        f"{c.name}:{c.type_text}"
                        for c in (t.columns or [])[:20]
                    ]
                    parts.append(f"{catalog}.{schema}.{t.name}: [{', '.join(cols)}]")
            except Exception:
                parts.append(f"{catalog}.{schema}: [indisponível]")

        return "\n".join(parts)

    def build_context(self, failure: dict, catalog: str = "medallion") -> dict:
        """Constrói contexto completo para o LLM provider."""
        run_id = failure["run_id"]
        codes = self.collect_notebook_code(run_id)
        schema = self.collect_schema_info(catalog=catalog)

        first_failed = failure["failed_tasks"][0]

        return {
            "failed_task": first_failed,
            "error_message": failure["errors"].get(first_failed, "Unknown"),
            "notebook_code": codes.get(first_failed, "[código não disponível]"),
            "schema_info": schema,
            "all_codes": codes,
            "pipeline_state": {
                "job_name": failure["job_name"],
                "job_id": failure["job_id"],
                "run_id": run_id,
                "failed_tasks": failure["failed_tasks"],
                "all_errors": failure["errors"],
                "timestamp": failure["timestamp"],
            },
        }
