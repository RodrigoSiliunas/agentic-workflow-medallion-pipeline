"""Upload de um arquivo local pra path no workspace Databricks via SDK.

Pra hotpatch de configs (observer_config.yaml etc) sem precisar redeploy
completo da saga.

Uso:
    docker exec -w /app/platform/backend -e PYTHONPATH=/app/platform/backend \\
        flowertex-backend uv run python scripts/vps_upload_workspace_file.py \\
        --user-email administrator@idlehub.com.br \\
        --source-path pipelines/pipeline-seguradora-whatsapp/observer_config.yaml \\
        --workspace-path /Shared/flowertex/agentic-workflow-medallion-pipeline/pipelines/pipeline-seguradora-whatsapp/observer_config.yaml
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

from sqlalchemy import select

from app.database.session import AsyncSessionLocal
from app.models.user import User
from app.services.credential_service import CredentialService


async def _resolve_creds(email: str) -> tuple[str, str]:
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(User).where(User.email == email))
        user = result.scalar_one_or_none()
        if not user:
            raise SystemExit(f"User nao encontrado: {email}")
        svc = CredentialService(db)
        host = await svc.get_decrypted(user.company_id, "databricks_host")
        token = await svc.get_decrypted(user.company_id, "databricks_token")
        if not host or not token:
            raise SystemExit("databricks_host/token nao configurado")
        return host, token


def _upload(host: str, token: str, source: Path, workspace_path: str) -> None:
    from databricks.sdk import WorkspaceClient
    from databricks.sdk.service.workspace import ImportFormat, Language

    w = WorkspaceClient(host=host, token=token)

    content = source.read_bytes()
    print(f"=== Source: {source} ({len(content)} bytes)")
    print(f"=== Target: {workspace_path}")

    # Garante que diretorios pai existem
    parent = "/".join(workspace_path.split("/")[:-1])
    try:
        w.workspace.mkdirs(parent)
    except Exception as exc:  # noqa: BLE001
        print(f"=== mkdirs warn (talvez ja exista): {exc}")

    # Tenta AUTO primeiro (pega yaml/json/raw .py como FILE). Se existir
    # um NOTEBOOK no path destino, AUTO falha com "type mismatch" — nesse
    # caso refaz upload como SOURCE+Python pra sobrescrever notebook.
    try:
        w.workspace.upload(
            path=workspace_path,
            content=content,
            format=ImportFormat.AUTO,
            overwrite=True,
        )
        print("=== Upload OK (AUTO)")
        return
    except Exception as exc:  # noqa: BLE001
        if "type mismatch" not in str(exc).lower():
            raise
        print(f"=== AUTO falhou ({exc}); retry como SOURCE+PYTHON (notebook)")

    w.workspace.upload(
        path=workspace_path,
        content=content,
        format=ImportFormat.SOURCE,
        language=Language.PYTHON,
        overwrite=True,
    )
    print("=== Upload OK (SOURCE+PYTHON)")


async def _main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--user-email", required=True)
    parser.add_argument("--source-path", required=True, help="Path local (relativo ao /app)")
    parser.add_argument("--workspace-path", required=True)
    args = parser.parse_args()

    host, token = await _resolve_creds(args.user_email)
    print(f"=== host={host}\n")

    source = Path("/app") / args.source_path
    if not source.exists():
        raise SystemExit(f"Source nao encontrado: {source}")

    _upload(host, token, source, args.workspace_path)


if __name__ == "__main__":
    try:
        asyncio.run(_main())
    except SystemExit:
        raise
    except Exception as exc:  # noqa: BLE001
        print(f"FATAL: {type(exc).__name__}: {exc}", file=sys.stderr)
        sys.exit(1)
