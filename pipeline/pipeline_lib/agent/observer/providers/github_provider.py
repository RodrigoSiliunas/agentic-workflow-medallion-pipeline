"""Provider Git: GitHub (via PyGithub)."""

from __future__ import annotations

import logging
from datetime import datetime

from pipeline_lib.agent.observer.providers import register_git_provider
from pipeline_lib.agent.observer.providers.base import (
    DiagnosisResult,
    GitProvider,
    PRResult,
    with_retry,
)

logger = logging.getLogger(__name__)


@register_git_provider("github")
class GitHubProvider(GitProvider):
    """Cria branches e PRs no GitHub via PyGithub."""

    def __init__(
        self,
        token: str = "",
        repo: str = "",
        base_branch: str = "dev",
    ):
        self._token = token
        self._repo_name = repo
        self._base_branch = base_branch

    @property
    def name(self) -> str:
        return "github"

    @with_retry(max_retries=3, base_delay=2.0)
    def create_fix_pr(
        self,
        diagnosis: DiagnosisResult,
        failed_task: str,
    ) -> PRResult:
        try:
            # Lazy import: optional dependency
            from github import Auth, Github
        except ImportError as e:
            raise ImportError(
                "PyGithub nao instalado. Instale com: pip install PyGithub"
            ) from e

        # Suporta fix em N arquivos via DiagnosisResult.normalized_fixes().
        # Retrocompativel com o formato singular (fixed_code + file_to_fix).
        fixes = diagnosis.normalized_fixes()
        if not fixes:
            raise ValueError(
                "DiagnosisResult nao contem fixes aplicaveis "
                "(fixes vazio e fixed_code/file_to_fix ausentes)"
            )

        gh = Github(auth=Auth.Token(self._token))
        repo = gh.get_repo(self._repo_name)

        # Branch unica baseada em timestamp
        ts = datetime.now().strftime("%Y%m%d-%H%M%S")
        task_slug = failed_task.replace("_", "-")
        branch_name = f"fix/agent-auto-{task_slug}-{ts}"

        # Criar branch a partir de main
        main_ref = repo.get_git_ref("heads/main")
        repo.create_git_ref(f"refs/heads/{branch_name}", main_ref.object.sha)

        # Um commit por arquivo (todos na mesma branch). O PR final
        # agrega todas as mudancas.
        applied_files: list[str] = []
        for fix in fixes:
            file_path = fix["file_path"]
            code = fix["code"]
            commit_msg = (
                f"fix: correcao automatica em {failed_task} ({file_path})\n\n"
                f"{diagnosis.fix_description}"
            )
            try:
                content = repo.get_contents(file_path, ref=branch_name)
                repo.update_file(
                    path=file_path,
                    message=commit_msg,
                    content=code,
                    sha=content.sha,
                    branch=branch_name,
                )
            except Exception:
                # Arquivo nao existe no branch — cria
                repo.create_file(
                    path=file_path,
                    message=commit_msg,
                    content=code,
                    branch=branch_name,
                )
            applied_files.append(file_path)

        # Garantir que base branch existe
        try:
            repo.get_branch(self._base_branch)
        except Exception:
            repo.create_git_ref(
                f"refs/heads/{self._base_branch}",
                main_ref.object.sha,
            )

        # PR com diagnostico
        conf = diagnosis.confidence
        emoji = "🟢" if conf >= 0.8 else "🟡" if conf >= 0.5 else "🔴"

        files_section = "\n".join(f"- `{p}`" for p in applied_files)
        title_suffix = (
            f" ({len(applied_files)} arquivos)" if len(applied_files) > 1 else ""
        )

        pr = repo.create_pull(
            title=f"fix: [{failed_task}] correcao automatica{title_suffix}",
            body=(
                f"## Correcao Automatica — Observer Agent\n\n"
                f"{emoji} **Confianca: {conf:.0%}** "
                f"(provider: {diagnosis.provider}, "
                f"model: {diagnosis.model})\n\n"
                f"### Problema\n{diagnosis.diagnosis}\n\n"
                f"### Causa Raiz\n{diagnosis.root_cause}\n\n"
                f"### Fix\n{diagnosis.fix_description}\n\n"
                f"### Arquivos modificados ({len(applied_files)})\n{files_section}\n\n"
                f"---\n"
                f"🤖 PR criado pelo Observer Agent "
                f"({diagnosis.provider}/{diagnosis.model})"
            ),
            head=branch_name,
            base=self._base_branch,
        )

        return PRResult(
            pr_url=pr.html_url,
            pr_number=pr.number,
            branch_name=branch_name,
        )

    def get_pr_status(self, pr_number: int) -> str:
        """Consulta o GitHub para saber se um PR esta open, merged ou closed.

        Usado pela logica de deduplicacao do Observer. Retorna 'unknown' em
        caso de erro para que o dedup adote o comportamento safe (skip).
        """
        if not pr_number:
            return "unknown"
        try:
            # Lazy import: optional dependency
            from github import Auth, Github
        except ImportError:
            return "unknown"

        try:
            gh = Github(auth=Auth.Token(self._token))
            repo = gh.get_repo(self._repo_name)
            pr = repo.get_pull(int(pr_number))
            if pr.merged:
                return "merged"
            # pr.state eh 'open' ou 'closed' no GitHub
            return pr.state or "unknown"
        except Exception as exc:
            logger.warning(f"Falha ao consultar PR #{pr_number}: {exc}")
            return "unknown"
