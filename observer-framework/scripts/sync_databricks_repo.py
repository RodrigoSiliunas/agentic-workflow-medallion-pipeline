"""Forca um Databricks Repo a puxar o head atual de uma branch.

Chamado pela GitHub Action `.github/workflows/observer-feedback.yml` quando um
PR do Observer e mergeado. O Observer escreve o fix no Git mas o
`/Repos/<user>/<repo>` em Databricks fica "dirty" se o usuario editou a
notebook direto pela UI (cenario E2E do teste manual). Forcar checkout aqui
limpa as edicoes locais e alinha workspace com Git.

Uso:
    python observer-framework/scripts/sync_databricks_repo.py \
        --repo-path "/Repos/user@example.com/agentic-workflow-medallion-pipeline" \
        --branch dev

    python observer-framework/scripts/sync_databricks_repo.py \
        --repo-path "/Repos/user@example.com/agentic-workflow-medallion-pipeline" \
        --branch dev --dry-run

Requer envs: DATABRICKS_HOST, DATABRICKS_TOKEN (ou autenticacao OAuth via
configuracao default do databricks-sdk).
"""

from __future__ import annotations

import argparse
import sys

from databricks.sdk import WorkspaceClient


def find_repo(workspace: WorkspaceClient, repo_path: str):
    """Retorna o Repo cujo `path` bate exatamente com `repo_path`.

    `w.repos.list()` nao filtra por path em todas as versoes do SDK,
    entao iteramos e comparamos exato — evita match parcial acidental.
    """
    target = repo_path.rstrip("/")
    for repo in workspace.repos.list():
        if (repo.path or "").rstrip("/") == target:
            return repo
    return None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--repo-path",
        required=True,
        help='Path absoluto do Repo em Databricks (ex: "/Repos/user/repo")',
    )
    parser.add_argument(
        "--branch",
        required=True,
        help="Branch para fazer checkout (ex: dev)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="So lista o Repo encontrado, nao executa o update",
    )
    args = parser.parse_args()

    workspace = WorkspaceClient()

    repo = find_repo(workspace, args.repo_path)
    if repo is None:
        print(f"ERRO: Repo nao encontrado em {args.repo_path}", file=sys.stderr)
        return 1

    print(f"Repo encontrado: id={repo.id} path={repo.path} branch_atual={repo.branch}")

    if args.dry_run:
        print("DRY-RUN: nao executou update")
        return 0

    workspace.repos.update(repo_id=repo.id, branch=args.branch)
    print(f"OK: Repo {repo.path} sincronizado com origin/{args.branch}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
