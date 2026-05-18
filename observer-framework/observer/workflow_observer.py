"""Workflow Observer — agente genérico que monitora workflows Databricks.

Detecta falhas em qualquer workflow do workspace, coleta contexto
completo (logs, código, schema) para enviar ao LLM provider.

Desacoplado de qualquer pipeline específico.
"""

from __future__ import annotations

import base64
import logging
import re
from datetime import datetime, timedelta

from databricks.sdk import WorkspaceClient
from databricks.sdk.service.workspace import ExportFormat

from observer.redaction import redact
from observer.triggering import extract_failed_task_keys

logger = logging.getLogger("workflow_observer")

# Captura tudo após o root do repo dentro do workspace. Funciona tanto
# pra deploy via saga (`/Shared/flowertex/<repo>/...`) quanto pra
# Databricks Repos (`/Repos/<user>/<repo>/...`).
_REPO_PATH_RE = re.compile(
    r"^/(?:Shared/[^/]+|Repos/[^/]+)/(?P<repo>[^/]+)/(?P<path>.*)$"
)


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

    def collect_notebook_workspace_paths(self, run_id: int) -> dict[str, str]:
        """Mapeia task_key -> notebook_path do workspace pra um run.

        Usado pelo auto-restore quando o LLM propoe fix igual a base
        e o caller precisa sobrescrever o arquivo no workspace.
        """
        paths: dict[str, str] = {}
        run = self.w.jobs.get_run(run_id=run_id)
        for task in run.tasks or []:
            if task.notebook_task:
                paths[task.task_key] = task.notebook_task.notebook_path
        return paths

    def restore_workspace_file(
        self,
        workspace_path: str,
        content: str | bytes,
        language: str = "PYTHON",
    ) -> None:
        """Sobrescreve um arquivo no workspace Databricks com `content`.

        Usado pelo auto-restore quando o LLM gerou um fix identico a base
        — significa que workspace divergiu (edicao manual via Databricks UI)
        e a correcao certa eh restaurar o conteudo da base no workspace.

        Args:
            workspace_path: path absoluto no workspace (ex:
                `/Shared/.../bronze/ingest`). Sem extensao .py — workspace
                identifica como notebook pelo language.
            content: bytes ou string do arquivo (assume UTF-8 se string).
            language: linguagem do notebook (PYTHON, SQL, SCALA, R).
        """
        from databricks.sdk.service.workspace import ImportFormat, Language

        content_bytes = content.encode("utf-8") if isinstance(content, str) else content
        b64 = base64.b64encode(content_bytes).decode("ascii")
        lang = getattr(Language, language.upper(), Language.PYTHON)

        self.w.workspace.import_(
            path=workspace_path,
            content=b64,
            format=ImportFormat.SOURCE,
            language=lang,
            overwrite=True,
        )
        logger.info(
            f"Workspace restaurado: {workspace_path} "
            f"({len(content_bytes)} bytes, language={lang.value})"
        )

    def collect_notebook_code(self, run_id: int) -> dict[str, str]:
        """Lê código fonte de cada notebook via Workspace API."""
        codes = {}
        run = self.w.jobs.get_run(run_id=run_id)

        for task in run.tasks or []:
            if not task.notebook_task:
                continue
            nb_path = task.notebook_task.notebook_path
            try:
                # SDK exige enum ExportFormat — string causa
                # `'str' object has no attribute 'value'` no caminho
                # interno do client (chama format.value).
                export = self.w.workspace.export(
                    path=nb_path, format=ExportFormat.SOURCE
                )
                if export.content:
                    code = base64.b64decode(export.content).decode("utf-8")
                    codes[task.task_key] = code
                    logger.info(f"Código: {task.task_key} ({len(code)} chars)")
            except Exception as e:
                codes[task.task_key] = f"[Erro ao ler {nb_path}: {e}]"
                logger.warning(f"Não leu {nb_path}: {e}")

        return codes

    def collect_git_reference(
        self,
        run_id: int,
        github_repo: str,
        github_token: str,
        branch: str = "main",
    ) -> dict[str, str]:
        """Busca código de cada notebook na branch base do GitHub.

        Cenário-alvo: user editou notebook direto no workspace (Databricks
        UI), código ficou divergente do git e o LLM precisa da referência
        funcional pra propor fix completo. Sem isso, LLM com só fragmento
        truncado se recusa a inventar o resto.

        Args:
            run_id: run Databricks que falhou
            github_repo: "owner/repo" (ex: rodrigosiliunas/agentic-workflow-medallion-pipeline)
            github_token: PAT classic com escopo de leitura
            branch: branch base (default main)

        Returns dict {task_key: code}. Vazio quando o path workspace nao
        bate com `/Shared/<x>/<repo>/...` ou `/Repos/<user>/<repo>/...`.
        """
        refs: dict[str, str] = {}
        if not github_repo or not github_token:
            logger.info("Git reference: sem github_repo/token, skip")
            return refs

        try:
            from github import Auth, Github
        except ImportError:
            logger.warning("Git reference: PyGithub nao instalado, skip")
            return refs

        run = self.w.jobs.get_run(run_id=run_id)
        gh = Github(auth=Auth.Token(github_token))
        repo = gh.get_repo(github_repo)

        for task in run.tasks or []:
            if not task.notebook_task:
                continue
            nb_path = task.notebook_task.notebook_path
            m = _REPO_PATH_RE.match(nb_path)
            if not m:
                logger.info(
                    f"Git reference: path {nb_path} fora do padrao "
                    "/Shared|/Repos, skip"
                )
                continue
            # `nb_path` aponta pra notebook sem extensao. Notebooks da
            # plataforma sao salvos como .py no repo.
            repo_path = f"{m.group('path')}.py"
            try:
                content = repo.get_contents(repo_path, ref=branch)
                # Pode ser list se for diretorio — mas notebook e arquivo
                if isinstance(content, list):
                    continue
                code = content.decoded_content.decode("utf-8")
                refs[task.task_key] = code
                logger.info(
                    f"Git reference: {task.task_key} = "
                    f"{repo_path}@{branch} ({len(code)} chars)"
                )
            except Exception as exc:  # noqa: BLE001
                logger.warning(
                    f"Git reference falhou pra {repo_path}@{branch}: {exc}"
                )

        return refs

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

    def build_context(
        self,
        failure: dict,
        catalog: str = "medallion",
        github_repo: str = "",
        github_token: str = "",
        git_reference_branch: str = "main",
    ) -> dict:
        """Constrói contexto completo para o LLM provider.

        Quando `github_repo`+`github_token` informados, tambem coleta o
        codigo de referencia do git (branch base) — usado pelo provider
        pra ajudar o LLM a reconstruir notebook quando workspace foi
        editado e fragmento ficou pequeno demais.
        """
        run_id = failure["run_id"]
        codes = self.collect_notebook_code(run_id)
        schema = self.collect_schema_info(catalog=catalog)
        git_refs: dict[str, str] = {}
        if github_repo and github_token:
            git_refs = self.collect_git_reference(
                run_id=run_id,
                github_repo=github_repo,
                github_token=github_token,
                branch=git_reference_branch,
            )

        first_failed = failure["failed_tasks"][0]

        # Resolver file_to_fix_hint do task que falhou — extrai path
        # repo-relative do notebook_path workspace (`/Shared/.../<repo>/X`
        # ou `/Repos/<user>/<repo>/X`). Sem isso, LLM hallucinava path
        # tentando combinar exemplo do prompt com o real (`/pipeline/`
        # segments extra apareciam).
        file_to_fix_hint = ""
        notebook_workspace_paths: dict[str, str] = {}
        try:
            run = self.w.jobs.get_run(run_id=run_id)
            for task in run.tasks or []:
                if not task.notebook_task:
                    continue
                nb_path = task.notebook_task.notebook_path
                notebook_workspace_paths[task.task_key] = nb_path
                if task.task_key == first_failed:
                    m = _REPO_PATH_RE.match(nb_path)
                    if m:
                        file_to_fix_hint = f"{m.group('path')}.py"
        except Exception as exc:  # noqa: BLE001
            logger.warning(f"Falha ao resolver file_to_fix_hint: {exc}")

        return {
            "failed_task": first_failed,
            "error_message": failure["errors"].get(first_failed, "Unknown"),
            "notebook_code": codes.get(first_failed, "[código não disponível]"),
            "reference_code": git_refs.get(first_failed, ""),
            "file_to_fix_hint": file_to_fix_hint,
            "notebook_workspace_paths": notebook_workspace_paths,
            "schema_info": schema,
            "all_codes": codes,
            "all_references": git_refs,
            "pipeline_state": {
                "job_name": failure["job_name"],
                "job_id": failure["job_id"],
                "run_id": run_id,
                "failed_tasks": failure["failed_tasks"],
                "all_errors": failure["errors"],
                "timestamp": failure["timestamp"],
            },
        }
