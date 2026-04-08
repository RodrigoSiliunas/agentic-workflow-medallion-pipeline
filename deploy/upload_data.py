"""Upload do Parquet Bronze para Databricks Volumes.

Uso: python deploy/upload_data.py <local_parquet_path>

Requer env vars: DATABRICKS_HOST, DATABRICKS_TOKEN
"""

import os
import sys

from databricks.sdk import WorkspaceClient


def upload(local_path: str):
    w = WorkspaceClient(
        host=os.environ["DATABRICKS_HOST"],
        token=os.environ["DATABRICKS_TOKEN"],
    )

    catalog = "medallion"
    volume_path = f"/Volumes/{catalog}/bronze/raw/"

    # Criar volume se nao existir
    try:
        w.volumes.create(
            catalog_name=catalog,
            schema_name="bronze",
            name="raw",
            volume_type="MANAGED",
            comment="Dados brutos Parquet",
        )
        print(f"Volume '{catalog}.bronze.raw' criado")
    except Exception as e:
        if "already exists" in str(e).lower():
            print(f"Volume '{catalog}.bronze.raw' ja existe")
        else:
            raise

    # Upload do arquivo
    filename = os.path.basename(local_path)
    dest_path = f"{volume_path}{filename}"

    print(f"Uploading {local_path} -> {dest_path}")
    with open(local_path, "rb") as f:
        w.files.upload(dest_path, f, overwrite=True)

    print(f"Upload completo: {dest_path}")
    print(f"Tamanho: {os.path.getsize(local_path) / 1024 / 1024:.1f} MB")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Uso: python deploy/upload_data.py conversations_bronze.parquet")
        sys.exit(1)
    upload(sys.argv[1])
