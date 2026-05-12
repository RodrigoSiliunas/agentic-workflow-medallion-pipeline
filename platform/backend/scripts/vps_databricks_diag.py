"""Diagnostico Databricks rodado dentro do container backend no VPS.

Pra usar quando user reporta falha em saga ou pipeline e o token Databricks
nao esta acessivel fora do VPS (creds armazenadas Fernet-encrypted no Postgres).

Pega credentials da empresa do user especificado via email, decripta com
ENCRYPTION_KEY do ambiente, e usa o databricks-sdk pra listar runs recentes
+ extrair erros de tasks que falharam.

Uso:
    docker exec flowertex-backend uv run python scripts/vps_databricks_diag.py \\
        --user-email administrator@idlehub.com.br \\
        --runs 5

NUNCA loga o token raw. Mascara como xxxx****yyyy.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.session import AsyncSessionLocal
from app.models.user import User
from app.services.credential_service import CredentialService


def _mask(value: str) -> str:
    if not value or len(value) < 8:
        return "****"
    return f"{value[:4]}****{value[-4:]}"


async def _resolve_company_id(db: AsyncSession, email: str) -> uuid.UUID:
    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()
    if not user:
        raise SystemExit(f"User nao encontrado: {email}")
    return user.company_id


async def _resolve_creds(db: AsyncSession, company_id: uuid.UUID) -> tuple[str, str]:
    svc = CredentialService(db)
    host = await svc.get_decrypted(company_id, "databricks_host")
    token = await svc.get_decrypted(company_id, "databricks_token")
    if not host or not token:
        raise SystemExit(
            f"databricks_host={bool(host)} databricks_token={bool(token)} — "
            "configurar em /settings"
        )
    return host, token


def _run_databricks_diag(host: str, token: str, runs_limit: int) -> None:
    from databricks.sdk import WorkspaceClient

    w = WorkspaceClient(host=host, token=token)

    print(f"=== Conectado: {host}")
    me = w.current_user.me()
    print(f"=== User: {me.user_name}\n")

    print("=== Jobs ===")
    jobs = list(w.jobs.list(limit=20))
    for j in jobs:
        print(f"  job_id={j.job_id}  name={j.settings.name if j.settings else '?'}")
    print()

    print(f"=== Ultimas {runs_limit} runs (qualquer job) ===")
    runs = list(w.jobs.list_runs(limit=runs_limit, expand_tasks=True))
    for r in runs:
        state = (
            f"{r.state.result_state or r.state.life_cycle_state}"
            if r.state
            else "?"
        )
        print(
            f"\n--- run_id={r.run_id}  job_id={r.job_id}  state={state}  "
            f"duration={r.run_duration}ms"
        )
        if not r.tasks:
            continue
        for t in r.tasks:
            ts = t.state.result_state if t.state and t.state.result_state else "?"
            ls = t.state.life_cycle_state if t.state else "?"
            print(f"    task={t.task_key}  result={ts}  cycle={ls}")
            if ts and "FAIL" in str(ts).upper():
                try:
                    out = w.jobs.get_run_output(run_id=t.run_id)
                    err = (out.error or "")[:1500]
                    err_trace = (out.error_trace or "")[:1500]
                    if err:
                        print(f"      ERROR: {err}")
                    if err_trace:
                        print(f"      TRACE: {err_trace}")
                except Exception as exc:  # noqa: BLE001
                    print(f"      (failed to fetch run_output: {exc})")


async def _main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--user-email", required=True)
    parser.add_argument("--runs", type=int, default=5)
    args = parser.parse_args()

    async with AsyncSessionLocal() as db:
        company_id = await _resolve_company_id(db, args.user_email)
        host, token = await _resolve_creds(db, company_id)

    print(f"=== company_id={company_id}")
    print(f"=== host={host}")
    print(f"=== token={_mask(token)}\n")

    _run_databricks_diag(host, token, args.runs)


if __name__ == "__main__":
    try:
        asyncio.run(_main())
    except SystemExit:
        raise
    except Exception as exc:  # noqa: BLE001
        print(f"FATAL: {type(exc).__name__}: {exc}", file=sys.stderr)
        sys.exit(1)
