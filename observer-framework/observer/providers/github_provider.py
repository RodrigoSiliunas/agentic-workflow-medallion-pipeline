"""Provider Git: GitHub (via PyGithub)."""

from __future__ import annotations

import logging
from datetime import datetime

from observer.providers import register_git_provider
from observer.providers.base import (
    DiagnosisResult,
    GitProvider,
    PRResult,
    with_retry,
)
from observer.providers.path_allowlist import (
    DisallowedPathError,
    validate_fixes,
)
from observer.redaction import redact

logger = logging.getLogger(__name__)

# Limite de chars do payload do fix dentro do `<details>` no body do PR
# de relatorio. GitHub corta body em 65_536 bytes; deixamos margem grande
# pra texto + metricas ficarem confortaveis.
_REPORT_PAYLOAD_LIMIT = 4096

REPORT_REASON_EXPLANATIONS: dict[str, str] = {
    "zero_diff": (
        "O workspace divergiu da base (provavelmente edicao manual via "
        "Databricks UI). O LLM propos conteudo identico ao que ja existe "
        "em `{base_branch}`."
    ),
    "low_confidence": (
        "Confianca do diagnostico abaixo do threshold configurado. "
        "Publicado para revisao humana antes de aplicar fix."
    ),
    "validation_failed": (
        "Fix proposto pelo LLM falhou na validacao estatica (syntax/imports). "
        "Detalhes acima."
    ),
}


class ZeroDiffError(ValueError):
    """Levantada quando o fix proposto pelo LLM e identico ao codigo
    da base branch — sinaliza que workspace divergiu da base e o
    caller pode optar por restaurar workspace <- base ao inves de
    abrir PR vazio.

    Herda de ValueError pra que o decorator `with_retry` nao retente
    (nao eh erro transient — eh estado valido detectado).

    Atributos:
      base_branch: branch base usada na comparacao (ex: dev)
      fixes: lista de {file_path, code} que o LLM propos — code aqui
             eh a versao "certa" (igual a base) que pode ser usada
             pra restaurar o workspace.
    """

    def __init__(self, base_branch: str, fixes: list[dict]):
        self.base_branch = base_branch
        self.fixes = fixes
        super().__init__(
            f"LLM propos conteudo identico a {base_branch} — workspace "
            "divergiu mas nao ha diff novo a aplicar. Caller deve restaurar "
            "workspace <- base usando os fixes anexados a esta exception."
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

        # Allowlist de paths — barra injection que tenta escrever em
        # .github/, infra/, deploy/, secrets, credenciais, chaves.
        try:
            fixes = validate_fixes(fixes)
        except DisallowedPathError as exc:
            logger.error(
                "GitProvider rejeitou fix do LLM: %s (task=%s, provider=%s)",
                exc,
                failed_task,
                diagnosis.provider,
            )
            raise

        gh = Github(auth=Auth.Token(self._token))
        repo = gh.get_repo(self._repo_name)

        # Path-exists guard: Observer SEMPRE corrige arquivo existente.
        # Se o LLM propos um path que nao existe na base, e quase certo
        # que ele hallucinou ("pipelines/.../pipeline/notebooks/..." com
        # /pipeline/ extra ja aconteceu). Falhar cedo evita poluir o
        # repo com arquivos fantasmas em paths invalidos.
        missing: list[str] = []
        for fix in fixes:
            file_path = fix["file_path"]
            try:
                repo.get_contents(file_path, ref=self._base_branch)
            except Exception:  # noqa: BLE001
                missing.append(file_path)
        if missing:
            raise ValueError(
                "LLM propos fix em path(s) que nao existem em "
                f"{self._base_branch}: {missing}. Path provavelmente "
                "hallucinado — confira contra arvore real do repo."
            )

        # Branch unica baseada em timestamp
        ts = datetime.now().strftime("%Y%m%d-%H%M%S")
        task_slug = failed_task.replace("_", "-")
        branch_name = f"fix/agent-auto-{task_slug}-{ts}"

        # Criar branch a partir do base_branch (default: dev). Antes
        # criava a partir de "main" mesmo quando o PR ia para dev, o
        # que gerava diff espurio se dev divergiu de main.
        base_ref = repo.get_git_ref(f"heads/{self._base_branch}")
        repo.create_git_ref(f"refs/heads/{branch_name}", base_ref.object.sha)

        # Um commit por arquivo (todos na mesma branch). O PR final
        # agrega todas as mudancas. Como o guard acima ja confirmou
        # existencia na base, aqui faz somente update_file (sem
        # fallback de create_file que mascarava hallucinacao de path).
        applied_files: list[str] = []
        for fix in fixes:
            file_path = fix["file_path"]
            code = fix["code"]
            commit_msg = (
                f"fix: correcao automatica em {failed_task} ({file_path})\n\n"
                f"{diagnosis.fix_description}"
            )
            content = repo.get_contents(file_path, ref=branch_name)
            repo.update_file(
                path=file_path,
                message=commit_msg,
                content=code,
                sha=content.sha,
                branch=branch_name,
            )
            applied_files.append(file_path)

        # Garantir que base branch existe. Se nao existir, cai pra main
        # como referencia inicial (so acontece em repos novos onde dev
        # ainda nao foi criado).
        try:
            repo.get_branch(self._base_branch)
        except Exception:
            fallback_ref = repo.get_git_ref("heads/main")
            repo.create_git_ref(
                f"refs/heads/{self._base_branch}",
                fallback_ref.object.sha,
            )

        # Guard rail: se o LLM propos conteudo identico ao que ja existe
        # na base, o PR vai abrir vazio (additions=0/deletions=0). Detecta
        # antes de criar o PR pra nao poluir a fila de revisao do humano.
        try:
            comparison = repo.compare(self._base_branch, branch_name)
            files_changed = list(getattr(comparison, "files", []) or [])
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                f"compare {self._base_branch}...{branch_name} falhou: {exc}. "
                "Seguindo com criacao do PR sem o guard de zero-diff."
            )
            files_changed = []
            comparison = None

        if comparison is not None and not files_changed:
            try:
                repo.get_git_ref(f"heads/{branch_name}").delete()
            except Exception as exc:  # noqa: BLE001
                logger.warning(
                    f"Falha ao limpar branch zero-diff {branch_name}: {exc}"
                )
            raise ZeroDiffError(self._base_branch, fixes)

        # PR com diagnostico
        conf = diagnosis.confidence
        emoji, _ = self._confidence_meta(conf)

        files_section = "\n".join(f"- `{p}`" for p in applied_files)
        title_suffix = (
            f" ({len(applied_files)} arquivos)" if len(applied_files) > 1 else ""
        )

        # PII redact nos campos do LLM antes de publicar no PR body.
        # diagnosis.* pode ecoar CPF/telefone/email vindos do erro original.
        safe_diagnosis = redact(diagnosis.diagnosis)
        safe_root_cause = redact(diagnosis.root_cause)
        safe_fix_desc = redact(diagnosis.fix_description)

        pr = repo.create_pull(
            title=f"fix: [{failed_task}] correcao automatica{title_suffix}",
            body=(
                f"## Correcao Automatica — Observer Agent\n\n"
                f"{emoji} **Confianca: {conf:.0%}** "
                f"(provider: {diagnosis.provider}, "
                f"model: {diagnosis.model})\n\n"
                f"### Problema\n{safe_diagnosis}\n\n"
                f"### Causa Raiz\n{safe_root_cause}\n\n"
                f"### Fix\n{safe_fix_desc}\n\n"
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

    @staticmethod
    def _confidence_meta(conf: float) -> tuple[str, str]:
        """Retorna (emoji, label) para uma confianca [0.0-1.0]."""
        if conf >= 0.8:
            return "🟢", "confidence-high"
        if conf >= 0.5:
            return "🟡", "confidence-medium"
        return "🔴", "confidence-low"

    def _build_report_body(
        self,
        diagnosis: DiagnosisResult,
        failed_task: str,
        reason: str,
        cost_usd: float,
    ) -> str:
        """Monta o markdown do PR de relatorio (tambem usado como conteudo
        do arquivo `.observer/reports/*.md`)."""
        emoji, _ = self._confidence_meta(diagnosis.confidence)
        conf = diagnosis.confidence

        # PII redact nos campos do LLM antes de publicar no body do PR.
        safe_diagnosis = redact(diagnosis.diagnosis or "")
        safe_root_cause = redact(diagnosis.root_cause or "")
        safe_fix_desc = redact(diagnosis.fix_description or "")

        reason_explanation = REPORT_REASON_EXPLANATIONS.get(
            reason,
            "Diagnostico publicado para revisao humana.",
        ).format(base_branch=self._base_branch)

        # Payload do fix proposto vira referencia (truncado em 4KB).
        fixes = diagnosis.normalized_fixes()
        if fixes:
            parts: list[str] = []
            for f in fixes:
                parts.append(f"# === {f['file_path']} ===\n{f['code']}")
            full_payload = "\n\n".join(parts)
            safe_payload = redact(full_payload)
            truncated = False
            if len(safe_payload) > _REPORT_PAYLOAD_LIMIT:
                safe_payload = safe_payload[:_REPORT_PAYLOAD_LIMIT]
                truncated = True
            trunc_marker = (
                f"\n\n... (truncado em {_REPORT_PAYLOAD_LIMIT} chars)"
                if truncated
                else ""
            )
            payload_section = (
                "<details>\n"
                "<summary>Payload do fix proposto (referencia)</summary>\n\n"
                "```\n"
                f"{safe_payload}{trunc_marker}\n"
                "```\n"
                "</details>"
            )
        else:
            payload_section = "_Sem fix proposto pelo LLM._"

        return (
            f"## Diagnostico Observer Agent — Report-Only\n\n"
            f"{emoji} **Confianca: {conf:.0%}** "
            f"(provider: {diagnosis.provider}, model: {diagnosis.model})\n\n"
            f"> **Por que nao ha code change?** {reason_explanation}\n\n"
            f"### Problema\n{safe_diagnosis}\n\n"
            f"### Causa Raiz\n{safe_root_cause}\n\n"
            f"### Fix proposto (descricao)\n{safe_fix_desc}\n\n"
            f"### Metricas\n"
            f"- Custo estimado: ${cost_usd:.4f}\n"
            f"- Tokens: in={diagnosis.input_tokens}, "
            f"out={diagnosis.output_tokens}\n"
            f"- Task: `{failed_task}`\n"
            f"- Reason code: `{reason}`\n\n"
            f"{payload_section}\n\n"
            f"---\n"
            f"Este PR e apenas um relatorio. Nao ha codigo a aplicar.\n"
            f"O workspace do Databricks permanece como esta — revise o "
            f"diagnostico e decida se quer alinhar manualmente.\n\n"
            f"🤖 Report criado pelo Observer Agent "
            f"({diagnosis.provider}/{diagnosis.model})"
        )

    def create_report_pr(
        self,
        diagnosis: DiagnosisResult,
        failed_task: str,
        reason: str,
        cost_usd: float = 0.0,
    ) -> PRResult:
        """Abre PR de relatorio (sem code change aplicavel).

        Commita 1 arquivo MD em `.observer/reports/{ts}-{task}-{reason}.md`
        em branch dedicada `observer/report-{reason}-{task}-{ts}` e abre
        PR rotulado `observer-report` + `no-code-change` + confianca.

        Diferente de create_fix_pr:
        - Sem @with_retry (caller decide retry; queremos sinal claro de falha).
        - Sem path_allowlist (path interno controlado pelo Observer).
        - Labels aplicadas em try/except (falha de label nao invalida o PR).
        """
        try:
            # Lazy import: optional dependency
            from github import Auth, Github
        except ImportError as e:
            raise ImportError(
                "PyGithub nao instalado. Instale com: pip install PyGithub"
            ) from e

        gh = Github(auth=Auth.Token(self._token))
        repo = gh.get_repo(self._repo_name)

        # Garantir que base branch existe (mesma logica do create_fix_pr).
        try:
            repo.get_branch(self._base_branch)
        except Exception:
            fallback_ref = repo.get_git_ref("heads/main")
            repo.create_git_ref(
                f"refs/heads/{self._base_branch}",
                fallback_ref.object.sha,
            )

        # Branch unica baseada em timestamp.
        ts = datetime.now().strftime("%Y%m%d-%H%M%S")
        task_slug = (failed_task or "unknown").replace("_", "-")
        reason_slug = (reason or "unknown").replace("_", "-")
        branch_name = f"observer/report-{reason_slug}-{task_slug}-{ts}"

        base_ref = repo.get_git_ref(f"heads/{self._base_branch}")
        repo.create_git_ref(f"refs/heads/{branch_name}", base_ref.object.sha)

        # Monta corpo do relatorio (markdown) — mesmo conteudo vai no
        # arquivo committado e no body do PR.
        report_md = self._build_report_body(
            diagnosis=diagnosis,
            failed_task=failed_task,
            reason=reason,
            cost_usd=cost_usd,
        )

        report_path = (
            f".observer/reports/{ts}-{task_slug}-{reason_slug}.md"
        )
        commit_msg = (
            f"report: [{failed_task}] diagnostico Observer ({reason})"
        )
        repo.create_file(
            path=report_path,
            message=commit_msg,
            content=report_md,
            branch=branch_name,
        )

        pr = repo.create_pull(
            title=(
                f"report: [{failed_task}] diagnostico sem code-change "
                f"({reason})"
            ),
            body=report_md,
            head=branch_name,
            base=self._base_branch,
        )

        # Labels — best-effort, falha aqui nao invalida o PR.
        _, conf_label = self._confidence_meta(diagnosis.confidence)
        try:
            repo.get_issue(pr.number).set_labels(
                "observer-report",
                "no-code-change",
                conf_label,
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                f"Falha ao aplicar labels no report PR #{pr.number}: "
                f"{exc}. PR criado sem labels."
            )

        return PRResult(
            pr_url=pr.html_url,
            pr_number=pr.number,
            branch_name=branch_name,
        )
