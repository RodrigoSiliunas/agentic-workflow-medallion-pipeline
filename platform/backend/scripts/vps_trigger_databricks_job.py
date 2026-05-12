"""Dispara um job Databricks rodando dentro do container backend no VPS.

Decripta o token Databricks da empresa do user via CredentialService,
usa databricks-sdk pra disparar `jobs.run_now`. Imprime run_id +
status inicial. Pareado com vps_databricks_diag.py.

Uso:
    docker exec -w /app/platform/backend -e PYTHONPATH=/app/platform/backend \\
        flowertex-backend uv run python scripts/vps_trigger_databricks_job.py \\
        --user-email administrator@idlehub.com.br \\
        --job-name medallion_pipeline_whatsapp

NUNCA loga o token raw — mascara como xxxx****yyyy.
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
        raise SystemExit("databricks_host/token nao configurado em /settings")
    return host, token


def _trigger_job(host: str, token: str, job_name: str | None, job_id: int | None) -> None:
    from databricks.sdk import WorkspaceClient

    w = WorkspaceClient(host=host, token=token)

    if job_id is None:
        # Resolver job_id por nome
        if not job_name:
            raise SystemExit("--job-name ou --job-id obrigatorio")
        jobs = list(w.jobs.list(limit=50, name=job_name))
        if not jobs:
            available = [j.settings.name for j in w.jobs.list(limit=50) if j.settings]
            raise SystemExit(
                f"Job '{job_name}' nao encontrado. Disponiveis: {available}"
            )
        job_id = jobs[0].job_id
        print(f"=== Job resolvido: name={job_name} id={job_id}")

    print(f"=== Disparando run_now em job_id={job_id}")
    run = w.jobs.run_now(job_id=job_id)
    print(f"=== Run criado: run_id={run.run_id}")
    print(
        "=== Acompanhar: "
        f"{host}/jobs/{job_id}/runs/{run.run_id}"
    )


async def _main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--user-email", required=True)
    parser.add_argument("--job-name", default=None)
    parser.add_argument("--job-id", type=int, default=None)
    args = parser.parse_args()

    async with AsyncSessionLocal() as db:
        company_id = await _resolve_company_id(db, args.user_email)
        host, token = await _resolve_creds(db, company_id)

    print(f"=== company_id={company_id}")
    print(f"=== host={host}")
    print(f"=== token={_mask(token)}\n")

    _trigger_job(host, token, args.job_name, args.job_id)


if __name__ == "__main__":
    try:
        asyncio.run(_main())
    except SystemExit:
        raise
    except Exception as exc:  # noqa: BLE001
        print(f"FATAL: {type(exc).__name__}: {exc}", file=sys.stderr)
        sys.exit(1)
