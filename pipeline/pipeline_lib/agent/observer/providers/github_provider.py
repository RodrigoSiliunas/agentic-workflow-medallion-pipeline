"""Provider Git: GitHub (via PyGithub)."""

from __future__ import annotations

from datetime import datetime

from pipeline_lib.agent.observer.providers import register_git_provider
from pipeline_lib.agent.observer.providers.base import (
    DiagnosisResult,
    GitProvider,
    PRResult,
)


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

    def create_fix_pr(
        self,
        diagnosis: DiagnosisResult,
        failed_task: str,
    ) -> PRResult:
        try:
            from github import Auth, Github
        except ImportError as e:
            raise ImportError(
                "PyGithub nao instalado. "
                "Instale com: pip install PyGithub"
            ) from e

        gh = Github(auth=Auth.Token(self._token))
        repo = gh.get_repo(self._repo_name)

        # Branch unica baseada em timestamp
        ts = datetime.now().strftime("%Y%m%d-%H%M%S")
        task_slug = failed_task.replace("_", "-")
        branch_name = f"fix/agent-auto-{task_slug}-{ts}"

        # Criar branch a partir de main
        main_ref = repo.get_git_ref("heads/main")
        repo.create_git_ref(
            f"refs/heads/{branch_name}", main_ref.object.sha
        )

        # Commit o fix
        file_path = diagnosis.file_to_fix or "unknown"
        commit_msg = (
            f"fix: correcao automatica em {failed_task}\n\n"
            f"{diagnosis.fix_description}"
        )

        try:
            content = repo.get_contents(file_path, ref=branch_name)
            repo.update_file(
                path=file_path,
                message=commit_msg,
                content=diagnosis.fixed_code or "",
                sha=content.sha,
                branch=branch_name,
            )
        except Exception:
            repo.create_file(
                path=file_path,
                message=commit_msg,
                content=diagnosis.fixed_code or "",
                branch=branch_name,
            )

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
        emoji = (
            "🟢" if conf >= 0.8 else "🟡" if conf >= 0.5 else "🔴"
        )

        pr = repo.create_pull(
            title=f"fix: [{failed_task}] correcao automatica",
            body=(
                f"## Correcao Automatica — Observer Agent\n\n"
                f"{emoji} **Confianca: {conf:.0%}** "
                f"(provider: {diagnosis.provider}, "
                f"model: {diagnosis.model})\n\n"
                f"### Problema\n{diagnosis.diagnosis}\n\n"
                f"### Causa Raiz\n{diagnosis.root_cause}\n\n"
                f"### Fix\n{diagnosis.fix_description}\n\n"
                f"### Arquivo\n`{file_path}`\n\n"
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
