"""Workflow Observer — agente generico que monitora workflows Databricks.

Detecta falhas em qualquer workflow do workspace, coleta contexto
completo (logs, codigo, schema) e aciona o LLM para diagnostico + PR.

Desacoplado do pipeline — funciona como workflow independente.
"""

import logging
from datetime import datetime, timedelta

from databricks.sdk import WorkspaceClient

logger = logging.getLogger("workflow_observer")


class WorkflowObserver:
    """Observa workflows Databricks e aciona agente AI em falhas."""

    def __init__(self, w: WorkspaceClient):
        self.w = w

    def find_recent_failures(
        self, hours: int = 1, workflow_name: str = None
    ) -> list[dict]:
        """Encontra runs que falharam nas ultimas N horas.

        Args:
            hours: janela de tempo para buscar falhas
            workflow_name: filtrar por nome do workflow (None = todos)

        Returns:
            Lista de dicts com job_id, run_id, job_name, failed_tasks, errors
        """
        failures = []
        start_time = int(
            (datetime.now() - timedelta(hours=hours)).timestamp() * 1000
        )

        # Listar todos os jobs (ou filtrar por nome)
        jobs = list(self.w.jobs.list(name=workflow_name))

        for job in jobs:
            # Buscar runs recentes
            runs = list(
                self.w.jobs.list_runs(
                    job_id=job.job_id,
                    start_time_from=start_time,
                    limit=5,
                )
            )

            for run in runs:
                result = str(run.state.result_state) if run.state else ""
                if "FAILED" in result or "SUCCESS_WITH_FAILURES" in result:
                    # Coletar detalhes das tasks que falharam
                    full_run = self.w.jobs.get_run(run_id=run.run_id)
                    failed_tasks = []
                    errors = {}

                    for task in full_run.tasks:
                        task_result = str(task.state.result_state) if task.state else ""
                        if "FAILED" in task_result:
                            try:
                                out = self.w.jobs.get_run_output(
                                    run_id=task.run_id
                                )
                                error = out.error or "Unknown error"
                            except Exception:
                                error = "Could not retrieve error"
                            failed_tasks.append(task.task_key)
                            errors[task.task_key] = error[:500]

                    if failed_tasks:
                        failures.append({
                            "job_id": job.job_id,
                            "job_name": job.settings.name,
                            "run_id": run.run_id,
                            "failed_tasks": failed_tasks,
                            "errors": errors,
                            "timestamp": str(run.start_time),
                        })

        return failures

    def collect_notebook_code(self, run_id: int) -> dict[str, str]:
        """Le o codigo fonte de cada notebook de um run.

        Usa o Databricks Workspace API para ler os notebooks
        diretamente do Repos — funciona com qualquer workflow.

        Returns:
            Dict {task_key: codigo_fonte}
        """
        codes = {}
        run = self.w.jobs.get_run(run_id=run_id)

        for task in run.tasks:
            if task.notebook_task:
                nb_path = task.notebook_task.notebook_path
                try:
                    # Exporta o notebook como SOURCE (codigo Python)
                    export = self.w.workspace.export(
                        path=nb_path, format="SOURCE"
                    )
                    if export.content:
                        import base64
                        code = base64.b64decode(export.content).decode("utf-8")
                        codes[task.task_key] = code
                        logger.info(
                            f"Codigo coletado: {task.task_key} "
                            f"({len(code)} chars)"
                        )
                except Exception as e:
                    codes[task.task_key] = f"[Erro ao ler {nb_path}: {e}]"
                    logger.warning(f"Nao leu {nb_path}: {e}")

        return codes

    def collect_schema_info(self, catalog: str = "medallion") -> str:
        """Coleta schema detalhado de todas as tabelas do catalogo.

        Returns:
            String formatada com tabela: [col:tipo, ...]
        """
        parts = []
        for schema in ["bronze", "silver", "gold", "pipeline"]:
            try:
                tables = list(
                    self.w.tables.list(
                        catalog_name=catalog, schema_name=schema
                    )
                )
                for t in tables:
                    cols = []
                    if t.columns:
                        cols = [
                            f"{c.name}:{c.type_text}"
                            for c in t.columns[:20]
                        ]
                    parts.append(
                        f"{catalog}.{schema}.{t.name}: [{', '.join(cols)}]"
                    )
            except Exception:
                parts.append(f"{catalog}.{schema}: [indisponivel]")
        return "\n".join(parts)

    def build_context(self, failure: dict) -> dict:
        """Constroi o contexto completo para o LLM.

        Combina: erros, codigo fonte, schema, estado do run.
        """
        run_id = failure["run_id"]
        codes = self.collect_notebook_code(run_id)
        schema = self.collect_schema_info()

        # Pegar codigo da primeira task que falhou
        first_failed = failure["failed_tasks"][0]
        notebook_code = codes.get(first_failed, "[codigo nao disponivel]")
        error_msg = failure["errors"].get(first_failed, "Unknown")

        return {
            "failed_task": first_failed,
            "error_message": error_msg,
            "notebook_code": notebook_code,
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
