"""Dump dos logs de uma run Databricks especifica (notebook output + stderr).

Pra debug do Observer quando ele marca SUCCESS mas a analise falhou
silenciosamente — precisa ver stdout do notebook pra entender o que
o LLM decidiu (ou nao decidiu).

Uso:
    docker exec -w /app/platform/backend -e PYTHONPATH=/app/platform/backend \\
        flowertex-backend uv run python scripts/vps_run_logs.py \\
        --user-email administrator@idlehub.com.br \\
        --run-id 700411706211202
"""

from __future__ import annotations

import argparse
import asyncio
import sys

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


def _dump(host: str, token: str, run_id: int) -> None:
    from databricks.sdk import WorkspaceClient

    w = WorkspaceClient(host=host, token=token)

    print(f"=== Run {run_id}")
    run = w.jobs.get_run(run_id=run_id)
    state = run.state
    print(f"=== State: {state.result_state if state else '?'} / {state.life_cycle_state if state else '?'}")
    print(f"=== Duration: {run.run_duration}ms")
    print(f"=== Job: {run.run_name}\n")

    for task in (run.tasks or []):
        print(f"=== Task: {task.task_key}")
        ts = task.state.result_state if task.state else "?"
        ls = task.state.life_cycle_state if task.state else "?"
        print(f"    state={ts} cycle={ls}")
        try:
            out = w.jobs.get_run_output(run_id=task.run_id)
        except Exception as exc:  # noqa: BLE001
            print(f"    (failed to get output: {exc})")
            continue
        if out.notebook_output:
            result = out.notebook_output.result
            truncated = out.notebook_output.truncated
            if result:
                print(f"    notebook_output.result ({'TRUNCATED' if truncated else 'full'}):")
                for line in str(result).splitlines():
                    print(f"      {line}")
        if out.error:
            print(f"    ERROR: {out.error[:2000]}")
        if out.error_trace:
            print(f"    TRACE: {out.error_trace[:3000]}")
        if out.logs:
            print(f"    logs ({'TRUNCATED' if out.logs_truncated else 'full'}):")
            for line in str(out.logs).splitlines()[-100:]:  # ultimas 100 linhas
                print(f"      {line}")
        print()


async def _main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--user-email", required=True)
    parser.add_argument("--run-id", type=int, required=True)
    args = parser.parse_args()

    host, token = await _resolve_creds(args.user_email)
    print(f"=== host={host}\n")

    _dump(host, token, args.run_id)


if __name__ == "__main__":
    try:
        asyncio.run(_main())
    except SystemExit:
        raise
    except Exception as exc:  # noqa: BLE001
        print(f"FATAL: {type(exc).__name__}: {exc}", file=sys.stderr)
        sys.exit(1)
