"""Modulo para criar PRs automaticos no GitHub com correcoes do agente."""

import os
from datetime import datetime

from github import Auth, Github


def get_github_client() -> Github:
    """Cria cliente GitHub. Falha se token nao configurado."""
    auth = Auth.Token(os.environ["GITHUB_TOKEN"])
    return Github(auth=auth)


def create_fix_pr(
    fix_description: str,
    diagnosis: str,
    file_path: str,
    fixed_code: str,
    failed_task: str,
    confidence: float,
) -> dict:
    """Cria branch, commita a correcao, e abre PR no GitHub.

    Retorna dict com: pr_url, pr_number, branch_name.
    """
    gh = get_github_client()
    repo_name = os.environ["GITHUB_REPO"]
    repo = gh.get_repo(repo_name)

    # Gerar nome de branch unico
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    branch_name = f"fix/agent-auto-{failed_task.replace('_', '-')}-{timestamp}"

    # Criar branch a partir de main (PRs vao para dev)
    main_ref = repo.get_git_ref("heads/main")
    repo.create_git_ref(f"refs/heads/{branch_name}", main_ref.object.sha)

    # Ler arquivo atual e atualizar com o fix
    try:
        file_content = repo.get_contents(file_path, ref=branch_name)
        repo.update_file(
            path=file_path,
            message=f"fix: correcao automatica em {failed_task}\n\n{fix_description}",
            content=fixed_code,
            sha=file_content.sha,
            branch=branch_name,
        )
    except Exception:
        # Arquivo nao existe — criar
        repo.create_file(
            path=file_path,
            message=f"fix: correcao automatica em {failed_task}\n\n{fix_description}",
            content=fixed_code,
            branch=branch_name,
        )

    # Criar PR
    confidence_emoji = "🟢" if confidence >= 0.8 else "🟡" if confidence >= 0.5 else "🔴"

    pr_body = f"""## Correcao Automatica do Agente de Pipeline

{confidence_emoji} **Confianca do agente: {confidence:.0%}**

### Problema Detectado
**Task que falhou:** `{failed_task}`

{diagnosis}

### Correcao Aplicada
{fix_description}

### Arquivo Modificado
`{file_path}`

### Revisao Necessaria
{"⚠️ **REVISAO HUMANA RECOMENDADA** — confianca abaixo de 80%" if confidence < 0.8 else "✅ Agente tem alta confianca nesta correcao, mas revisao e sempre recomendada."}

---
🤖 PR criado automaticamente pelo **Pipeline Agent** via Claude API.
"""

    # PRs do agente vao para dev (nunca direto para main)
    base_branch = "dev"
    try:
        repo.get_branch(base_branch)
    except Exception:
        # Se branch dev nao existe, cria a partir de main
        repo.create_git_ref(f"refs/heads/{base_branch}", main_ref.object.sha)

    pr = repo.create_pull(
        title=f"fix: [{failed_task}] correcao automatica do agente",
        body=pr_body,
        head=branch_name,
        base=base_branch,
    )

    return {
        "pr_url": pr.html_url,
        "pr_number": pr.number,
        "branch_name": branch_name,
    }
