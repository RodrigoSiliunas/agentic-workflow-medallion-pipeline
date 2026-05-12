"""Executa query SQL via Databricks SQL Warehouse rodando no container backend.

Pra debugar o 400 Bad Request que o bot reporta ao tentar contar linhas
da bronze. Lista warehouses, inicia se parado, executa query.

Uso:
    docker exec -w /app/platform/backend -e PYTHONPATH=/app/platform/backend \\
        flowertex-backend uv run python scripts/vps_sql_query.py \\
        --user-email administrator@idlehub.com.br \\
        --query "SELECT COUNT(*) FROM medallion.bronze.conversations"
"""

from __future__ import annotations

import argparse
import asyncio
import sys
import time
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.session import AsyncSessionLocal
from app.models.user import User
from app.services.credential_service import CredentialService


def _mask(v: str) -> str:
    return f"{v[:4]}****{v[-4:]}" if v and len(v) >= 8 else "****"


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


def _ensure_warehouse_running(w, warehouse_id: str) -> None:
    wh = w.warehouses.get(warehouse_id)
    state = str(wh.state)
    print(f"=== Warehouse {warehouse_id}: state={state}")
    if "RUNNING" in state:
        return
    print("=== Iniciando warehouse...")
    w.warehouses.start(warehouse_id)
    for i in range(60):
        time.sleep(5)
        wh = w.warehouses.get(warehouse_id)
        if "RUNNING" in str(wh.state):
            print(f"=== Warehouse pronto apos {(i + 1) * 5}s")
            return
    raise SystemExit("Warehouse nao subiu em 5min")


def _run(host: str, token: str, query: str, warehouse_id: str | None) -> None:
    from databricks.sdk import WorkspaceClient
    from databricks.sdk.service.sql import StatementState

    w = WorkspaceClient(host=host, token=token)

    print("=== SQL Warehouses disponiveis:")
    warehouses = list(w.warehouses.list())
    for wh in warehouses:
        print(f"  id={wh.id} name={wh.name} state={wh.state} size={wh.cluster_size}")

    if not warehouses:
        raise SystemExit("Nenhum SQL warehouse no workspace")

    if not warehouse_id:
        warehouse_id = warehouses[0].id
        print(f"\n=== Usando primeiro warehouse: {warehouse_id}")

    _ensure_warehouse_running(w, warehouse_id)

    print(f"\n=== Executando query:\n{query}\n")
    resp = w.statement_execution.execute_statement(
        warehouse_id=warehouse_id,
        statement=query,
        wait_timeout="30s",
    )

    if resp.status and resp.status.state == StatementState.FAILED:
        err = resp.status.error
        print(f"FAILED: {err.message if err else 'unknown'}")
        if err:
            print(f"error_code: {err.error_code}")
        raise SystemExit(1)

    if resp.result and resp.result.data_array:
        print("=== Resultado:")
        for row in resp.result.data_array:
            print(f"  {row}")
    else:
        print(f"=== Sem rows. State: {resp.status.state if resp.status else '?'}")


async def _main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--user-email", required=True)
    parser.add_argument("--query", required=True)
    parser.add_argument("--warehouse-id", default=None)
    args = parser.parse_args()

    host, token = await _resolve_creds(args.user_email)
    print(f"=== host={host}")
    print(f"=== token={_mask(token)}\n")

    _run(host, token, args.query, args.warehouse_id)


if __name__ == "__main__":
    try:
        asyncio.run(_main())
    except SystemExit:
        raise
    except Exception as exc:  # noqa: BLE001
        print(f"FATAL: {type(exc).__name__}: {exc}", file=sys.stderr)
        sys.exit(1)
