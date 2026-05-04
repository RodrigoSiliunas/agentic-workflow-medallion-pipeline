"""Drop catalog medallion + external_location + storage_credential no Databricks.

Le credentials da plataforma (Postgres + Fernet decrypt) e roda DROP via SDK.
"""

from __future__ import annotations

import asyncio
import os

os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://postgres:postgres@postgres:5432/flowertex")
os.environ.setdefault("REDIS_URL", "redis://redis:6379/0")


async def main():
    from sqlalchemy import select

    from app.database.session import AsyncSessionLocal
    from app.models.company import Company
    from app.services.credential_service import CredentialService

    async with AsyncSessionLocal() as db:
        company = (await db.execute(select(Company).limit(1))).scalar_one_or_none()
        if not company:
            print("nenhuma company")
            return
        cs = CredentialService(db)
        creds = await cs.get_all_decrypted(company.id)
        host = creds.get("databricks_host")
        token = creds.get("databricks_token")
        if not host or not token:
            print(f"creds incompletas: host={host}, token={'set' if token else 'MISSING'}")
            return
        print(f"company={company.name}, host={host}")

    from databricks.sdk import WorkspaceClient
    w = WorkspaceClient(host=host, token=token)

    # 1. Drop catalog medallion (cascade)
    try:
        w.catalogs.delete(name="medallion", force=True)
        print("CATALOG medallion DROPPED")
    except Exception as e:
        print(f"catalog drop: {e}")

    # 2. Drop external locations
    try:
        for el in w.external_locations.list():
            if "medallion" in (el.name or "").lower():
                w.external_locations.delete(name=el.name, force=True)
                print(f"EXTERNAL LOCATION {el.name} DROPPED")
    except Exception as e:
        print(f"external_locations: {e}")

    # 3. Drop storage credentials
    try:
        for sc in w.storage_credentials.list():
            if "medallion" in (sc.name or "").lower():
                w.storage_credentials.delete(name=sc.name, force=True)
                print(f"STORAGE CREDENTIAL {sc.name} DROPPED")
    except Exception as e:
        print(f"storage_credentials: {e}")

    # 4. Workflow + cluster
    try:
        for j in w.jobs.list():
            if "medallion" in (j.settings.name or "").lower():
                w.jobs.delete(job_id=j.job_id)
                print(f"JOB {j.settings.name} DELETED")
    except Exception as e:
        print(f"jobs: {e}")

    try:
        for c in w.clusters.list():
            if "medallion" in (c.cluster_name or "").lower():
                w.clusters.permanent_delete(cluster_id=c.cluster_id)
                print(f"CLUSTER {c.cluster_name} DELETED")
    except Exception as e:
        print(f"clusters: {e}")

    print("DONE")


asyncio.run(main())
