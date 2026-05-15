"""Lista users + empresas via SQLAlchemy. Roda dentro do container.

Uso:
    docker exec -w /app/platform/backend -e PYTHONPATH=/app/platform/backend \\
        flowertex-backend uv run python scripts/vps_list_users.py
"""

from __future__ import annotations

import asyncio
import sys

from sqlalchemy import select

from app.database.session import AsyncSessionLocal
from app.models.company import Company
from app.models.user import User


async def _main() -> None:
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(User, Company).join(Company, Company.id == User.company_id)
        )
        rows = result.all()
        if not rows:
            print("=== Sem users cadastrados.")
            return
        print(f"=== {len(rows)} user(s) cadastrado(s):\n")
        for user, company in rows:
            print(
                f"  email={user.email}\n"
                f"    role={user.role}\n"
                f"    active={user.is_active}\n"
                f"    company={company.name} ({company.slug})\n"
                f"    created_at={user.created_at}\n"
            )


if __name__ == "__main__":
    try:
        asyncio.run(_main())
    except Exception as exc:  # noqa: BLE001
        print(f"FATAL: {type(exc).__name__}: {exc}", file=sys.stderr)
        sys.exit(1)
