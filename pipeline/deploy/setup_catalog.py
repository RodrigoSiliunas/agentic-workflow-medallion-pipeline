"""Cria o Unity Catalog + schemas para o pipeline.

Uso: python deploy/setup_catalog.py

Requer env vars: DATABRICKS_HOST, DATABRICKS_TOKEN
"""

import os

from databricks.sdk import WorkspaceClient


def setup():
    w = WorkspaceClient(
        host=os.environ["DATABRICKS_HOST"],
        token=os.environ["DATABRICKS_TOKEN"],
    )

    print(f"Conectado como: {w.current_user.me().user_name}")

    # Criar catalog
    catalog = "medallion"
    try:
        w.catalogs.create(name=catalog, comment="Pipeline Medallion WhatsApp Insurance")
        print(f"Catalog '{catalog}' criado")
    except Exception as e:
        if "already exists" in str(e).lower():
            print(f"Catalog '{catalog}' ja existe")
        else:
            raise

    # Criar schemas
    for schema in ["bronze", "silver", "gold", "pipeline"]:
        try:
            w.schemas.create(name=schema, catalog_name=catalog, comment=f"Camada {schema}")
            print(f"  Schema '{catalog}.{schema}' criado")
        except Exception as e:
            if "already exists" in str(e).lower():
                print(f"  Schema '{catalog}.{schema}' ja existe")
            else:
                raise

    print("\nSetup completo! Schemas disponiveis:")
    print(f"  - {catalog}.bronze")
    print(f"  - {catalog}.silver")
    print(f"  - {catalog}.gold")
    print(f"  - {catalog}.pipeline")


if __name__ == "__main__":
    setup()
