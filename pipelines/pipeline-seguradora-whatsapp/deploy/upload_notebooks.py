"""Faz upload de notebooks/arquivos ao workspace Databricks via SDK.

Usado pelo GitHub Actions para sincronizar arquivos alterados em PRs
pipeline-editor/* com o workspace Databricks antes de disparar o ETL.

Uso:
    python deploy/upload_notebooks.py <arquivo1> [<arquivo2> ...]

Requer env vars: DATABRICKS_HOST, DATABRICKS_TOKEN

Mapeamento de paths (espelha observer-feedback.yml):
    pipelines/...notebooks/bronze/ingest.py
        -> /Shared/flowertex/agentic-workflow-medallion-pipeline/pipelines/.../notebooks/bronze/ingest

Arquivos que nao existem localmente sao pulados com aviso (ex: delecao).
"""

import os
import sys
from pathlib import Path

from databricks.sdk import WorkspaceClient
from databricks.sdk.service.workspace import ImportFormat, Language

WORKSPACE_BASE = "/Shared/flowertex/agentic-workflow-medallion-pipeline"


def _workspace_path(src: str) -> str:
    """Converte path local em path no workspace Databricks."""
    if src.endswith(".py") and "/notebooks/" in src:
        return f"{WORKSPACE_BASE}/{src[:-3]}"
    return f"{WORKSPACE_BASE}/{src}"


def upload(w: WorkspaceClient, source: Path, workspace_path: str) -> None:
    content = source.read_bytes()
    print(f"==> {source} ({len(content)} bytes) -> {workspace_path}")

    parent = "/".join(workspace_path.split("/")[:-1])
    try:
        w.workspace.mkdirs(parent)
    except Exception as exc:  # noqa: BLE001
        print(f"    mkdirs warn (ja existe?): {exc}")

    is_notebook = "/notebooks/" in str(source) and str(source).endswith(".py")

    if is_notebook:
        w.workspace.upload(
            path=workspace_path,
            content=content,
            format=ImportFormat.SOURCE,
            language=Language.PYTHON,
            overwrite=True,
        )
    else:
        w.workspace.upload(
            path=workspace_path,
            content=content,
            format=ImportFormat.AUTO,
            overwrite=True,
        )
    print(f"    OK")


def main(files: list[str]) -> int:
    w = WorkspaceClient(
        host=os.environ["DATABRICKS_HOST"],
        token=os.environ["DATABRICKS_TOKEN"],
    )

    errors: list[str] = []
    for src in files:
        src = src.strip()
        if not src:
            continue
        path = Path(src)
        if not path.exists():
            print(f"SKIP (nao encontrado): {src}")
            continue
        try:
            upload(w, path, _workspace_path(src))
        except Exception as exc:  # noqa: BLE001
            print(f"ERRO ao fazer upload de {src}: {exc}", file=sys.stderr)
            errors.append(src)

    if errors:
        print(f"\n{len(errors)} arquivo(s) falharam: {errors}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Uso: python deploy/upload_notebooks.py <arquivo1> [<arquivo2> ...]")
        sys.exit(1)
    sys.exit(main(sys.argv[1:]))
