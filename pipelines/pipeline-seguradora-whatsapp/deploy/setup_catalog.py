"""Setup do Unity Catalog para o pipeline Medallion.

Fluxo (adaptavel):
  1. Storage Credential + External Location (se AWS integrado)
  2. Catalog 'medallion' (Default Storage ou com managed location)
  3. Schemas: bronze, silver, gold, pipeline
  4. Volume: pipeline.tmp (temp storage)

Uso: python deploy/setup_catalog.py

Requer env vars:
  DATABRICKS_HOST    — URL do workspace
  DATABRICKS_TOKEN   — Personal Access Token

Opcionais (se AWS integrado via Marketplace):
  AWS_IAM_ROLE_ARN   — ARN da role cross-account do Databricks
  S3_BUCKET_URL      — URL do bucket (ex: s3://namastex-medallion-datalake)
"""

import os
import sys
import time

from databricks.sdk import WorkspaceClient
from databricks.sdk.service.catalog import AwsIamRoleRequest

CATALOG_NAME = "medallion"
CREDENTIAL_NAME = "medallion-s3-credential"
LOCATION_NAME = "medallion-datalake"
SCHEMAS = ["bronze", "silver", "gold", "pipeline", "observer"]


def get_env(key: str, required: bool = True) -> str:
    val = os.environ.get(key, "").strip()
    if not val and required:
        print(f"ERRO: env var '{key}' nao definida")
        sys.exit(1)
    return val


def step_storage_credential(w: WorkspaceClient, role_arn: str):
    """Cria Storage Credential (requer AWS integration)."""
    print("\n[1/5] Storage Credential")
    if not role_arn:
        print("  SKIP: AWS_IAM_ROLE_ARN nao configurado")
        return

    existing = list(w.storage_credentials.list())
    for cred in existing:
        if cred.name == CREDENTIAL_NAME:
            if cred.aws_iam_role and cred.aws_iam_role.role_arn == role_arn:
                print(f"  '{CREDENTIAL_NAME}' ja existe — skip")
                return
            else:
                print(f"  ERRO: '{CREDENTIAL_NAME}' existe com config DIFERENTE!")
                sys.exit(1)

    try:
        w.storage_credentials.create(
            name=CREDENTIAL_NAME,
            aws_iam_role=AwsIamRoleRequest(role_arn=role_arn),
            comment="Acesso S3 para pipeline Medallion",
        )
        print(f"  '{CREDENTIAL_NAME}' criado (role: {role_arn})")
    except Exception as e:
        print(f"  WARN: Nao foi possivel criar Storage Credential: {e}")
        print("  Continuando sem External Location (usara Default Storage)")


def step_external_location(w: WorkspaceClient, s3_url: str):
    """Cria External Location (requer Storage Credential)."""
    print("\n[2/5] External Location")
    if not s3_url:
        print("  SKIP: S3_BUCKET_URL nao configurado")
        return

    existing = list(w.external_locations.list())
    for loc in existing:
        if loc.name == LOCATION_NAME:
            if loc.url.rstrip("/") == s3_url.rstrip("/"):
                print(f"  '{LOCATION_NAME}' ja existe — skip")
                return
            else:
                print(f"  ERRO: '{LOCATION_NAME}' existe com URL DIFERENTE!")
                sys.exit(1)

    try:
        w.external_locations.create(
            name=LOCATION_NAME, url=s3_url,
            credential_name=CREDENTIAL_NAME,
            comment="Data lake S3 do pipeline Medallion",
        )
        print(f"  '{LOCATION_NAME}' criado ({s3_url})")
    except Exception as e:
        print(f"  WARN: Nao foi possivel criar External Location: {e}")


def step_catalog(w: WorkspaceClient, warehouse_id: str, s3_url: str):
    """Cria catalog via SQL (suporta Default Storage)."""
    print("\n[3/5] Catalog")
    result = w.statement_execution.execute_statement(
        warehouse_id=warehouse_id,
        statement=f"CREATE CATALOG IF NOT EXISTS {CATALOG_NAME} "
                  f"COMMENT 'Pipeline Medallion - WhatsApp Insurance Analytics'",
        wait_timeout="30s",
    )
    if result.status.error:
        print(f"  ERRO: {result.status.error.message}")
        sys.exit(1)
    print(f"  Catalog '{CATALOG_NAME}' OK")


def step_schemas(w: WorkspaceClient, warehouse_id: str):
    """Cria schemas via SQL."""
    print("\n[4/5] Schemas")
    for schema in SCHEMAS:
        result = w.statement_execution.execute_statement(
            warehouse_id=warehouse_id,
            statement=f"CREATE SCHEMA IF NOT EXISTS {CATALOG_NAME}.{schema} "
                      f"COMMENT 'Camada {schema}'",
            wait_timeout="30s",
        )
        if result.status.error:
            print(f"  ERRO {schema}: {result.status.error.message}")
        else:
            print(f"  Schema '{CATALOG_NAME}.{schema}' OK")


def step_volume(w: WorkspaceClient, warehouse_id: str):
    """Cria volume para temp storage."""
    print("\n[5/5] Volume")
    result = w.statement_execution.execute_statement(
        warehouse_id=warehouse_id,
        statement=f"CREATE VOLUME IF NOT EXISTS {CATALOG_NAME}.pipeline.tmp "
                  "COMMENT 'Temp storage for pipeline'",
        wait_timeout="30s",
    )
    if result.status.error:
        print(f"  WARN: {result.status.error.message}")
    else:
        print("  Volume 'medallion.pipeline.tmp' OK")


def setup():
    host = get_env("DATABRICKS_HOST")
    token = get_env("DATABRICKS_TOKEN")
    role_arn = get_env("AWS_IAM_ROLE_ARN", required=False)
    s3_url = get_env("S3_BUCKET_URL", required=False)

    print("=" * 60)
    print("Databricks Unity Catalog Setup")
    print("=" * 60)
    print(f"  Host:     {host}")
    if role_arn:
        print(f"  Role ARN: {role_arn}")
    if s3_url:
        print(f"  S3 URL:   {s3_url}")

    w = WorkspaceClient(host=host, token=token)
    user = w.current_user.me()
    print(f"  User:     {user.user_name}")

    # Encontrar SQL warehouse
    warehouses = list(w.warehouses.list())
    if not warehouses:
        print("ERRO: Nenhum SQL Warehouse encontrado")
        sys.exit(1)

    wh = warehouses[0]
    if str(wh.state) != "State.RUNNING":
        print(f"  Starting warehouse '{wh.name}'...")
        w.warehouses.start(wh.id)
        for _ in range(30):
            time.sleep(5)
            wh = w.warehouses.get(wh.id)
            if str(wh.state) == "State.RUNNING":
                break
    print(f"  Warehouse: {wh.name} ({wh.id})")

    step_storage_credential(w, role_arn)
    step_external_location(w, s3_url)
    step_catalog(w, wh.id, s3_url)
    step_schemas(w, wh.id)
    step_volume(w, wh.id)

    print("\n" + "=" * 60)
    print("Setup completo!")
    print("=" * 60)
    print(f"  Catalog:  {CATALOG_NAME}")
    for s in SCHEMAS:
        print(f"  Schema:   {CATALOG_NAME}.{s}")
    if s3_url:
        print(f"  S3:       {s3_url}")
    print("\nProximo: python deploy/upload_data.py <parquet_path>")


if __name__ == "__main__":
    setup()
